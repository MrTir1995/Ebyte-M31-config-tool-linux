"""Bounded, opt-in, READ-ONLY acceptance probe for the connected M31.

Ordinary discovery never connects to hardware. Explicit invocation:

    M31_HARDWARE_READ_TEST=192.168.3.7 .venv/bin/python -m unittest tests.test_hardware -v

Also set M31_HARDWARE_AI=1 to probe the three documented AI start addresses,
and M31_HARDWARE_DEVICE_INFO=1 to read the documented parameter/status catalog.
These are raw words, not an inferred extension map, channel map, or scaling.
The exact IPv4 endpoint must be explicitly supplied in M31_HARDWARE_READ_TEST;
port 502 and unit 1 are used. Timeout is 2 seconds with no retries. Protocol
exceptions are reported as unsupported/unproven reads. Transport failures
abort the remaining reads and fail with endpoint details. No output,
configuration, firmware, reset, or network writes are performed.

"""

import ipaddress
import os
import unittest
from unittest.mock import Mock

from m31tool.core import (
    DI_START,
    DO_START,
    FILTER_AI_ADDRESS,
    FILTER_DI_ADDRESS,
    ModbusConnectionError,
    ModbusResponseError,
    ModbusSession,
)
from m31tool.device import read_device_info


HOST = os.environ.get("M31_HARDWARE_READ_TEST", "192.168.3.7")
PORT = 502
UNIT_ID = 1
ENDPOINT = f"{HOST}:{PORT} unit {UNIT_ID}"


def read_probe(session, *, include_ai=False, report=print):
    """Read only the allowed ranges once, stopping on a transport failure."""
    requests = [
        ("host DI", "read_discrete_inputs", DI_START, 8),
        ("host DO", "read_coils", DO_START, 8),
        ("AI filter", "read_holding_registers", FILTER_AI_ADDRESS, 1),
        ("DI filter", "read_holding_registers", FILTER_DI_ADDRESS, 1),
    ]
    if include_ai:
        requests.extend([
            ("AI integer raw", "read_input_registers", 0, 1),
            ("AI IEEE754 raw words", "read_input_registers", 1000, 2),
            ("AI process raw", "read_input_registers", 3000, 1),
        ])
    results, errors = {}, {}
    for label, method, address, count in requests:
        context = f"{ENDPOINT} {label}: {method} address={address} count={count}"
        try:
            values = getattr(session, method)(address, count)
        except ModbusResponseError as exc:
            errors[label] = str(exc)
            report(f"{context} -> RESPONSE ERROR: {exc}")
        except ModbusConnectionError as exc:
            report(f"{context} -> TRANSPORT FAILURE; remaining reads aborted: {exc}")
            raise
        else:
            results[label] = values
            report(f"{context} -> {values}")
    return results, errors


@unittest.skipUnless(
    os.environ.get("M31_HARDWARE_READ_TEST"),
    "Live M31 reads disabled; explicitly set M31_HARDWARE_READ_TEST to one IPv4 address.",
)
class ConnectedM31ReadTests(unittest.TestCase):
    def test_bounded_documented_reads(self):
        try:
            ipaddress.IPv4Address(HOST)
        except ipaddress.AddressValueError as exc:
            self.fail(f"M31_HARDWARE_READ_TEST must be one IPv4 address: {exc}")
        session = ModbusSession(unit_id=UNIT_ID, timeout=2.0)
        self.addCleanup(session.close)
        try:
            session.open_tcp(HOST, PORT)
            print(f"\nConnected to {ENDPOINT}; read-only probe, no retries.", flush=True)
            results, errors = read_probe(
                session, include_ai=os.environ.get("M31_HARDWARE_AI") == "1",
                report=lambda message: print(message, flush=True),
            )
        except ModbusConnectionError as exc:
            self.fail(f"Hardware connection/exchange failed at {ENDPOINT}: {exc}")
        for label in ("host DI", "host DO"):
            self.assertIn(label, results, f"{ENDPOINT}: {label} unproven: {errors}")
            self.assertEqual(len(results[label]), 8)
        if os.environ.get("M31_HARDWARE_DEVICE_INFO") == "1":
            info = read_device_info(session)
            self.assertTrue(info["read_only"])
            print("Documented device parameters/status (raw words):", flush=True)
            for field in info["fields"]:
                print(
                    f"  {field['key']} @ 0x{field['address']:04X}: "
                    f"{field['raw_hex']} ({field['decoded'] or 'raw only'})",
                    flush=True,
                )
        print(
            "Acceptance: host DI/DO reads succeeded. Optional register exceptions "
            "do not prove an extension layout. AI words and expansion bitmap are "
            "raw; no channel map is inferred. No writes, physical I/O effects, "
            "RTU, AI scaling/word order, or full Windows parity were tested.",
            flush=True,
        )


class HardwareProbeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock(spec=ModbusSession)
        self.session.read_discrete_inputs.return_value = [False] * 8
        self.session.read_coils.return_value = [False] * 8
        self.session.read_holding_registers.return_value = [6]
        self.session.read_input_registers.side_effect = [[0], [0, 0], [0]]
        self.messages = []

    def test_default_probe_only_reads_host_and_filters(self):
        results, errors = read_probe(self.session, report=self.messages.append)
        self.assertEqual(errors, {})
        self.assertEqual(len(results), 4)
        self.assertEqual(
            [(call[0], call[1]) for call in self.session.method_calls],
            [
                ("read_discrete_inputs", (0, 8)),
                ("read_coils", (0, 8)),
                ("read_holding_registers", (3490, 1)),
                ("read_holding_registers", (3491, 1)),
            ],
        )

    def test_ai_probe_only_reads_documented_start_addresses(self):
        read_probe(self.session, include_ai=True, report=self.messages.append)
        self.assertEqual(
            [call.args for call in self.session.read_input_registers.call_args_list],
            [(0, 1), (1000, 2), (3000, 1)],
        )
        self.session.write_coil.assert_not_called()
        self.session.write_register.assert_not_called()
        self.session.open_tcp.assert_not_called()
        self.session.open_rtu.assert_not_called()

    def test_protocol_exception_is_reported_not_retried(self):
        self.session.read_holding_registers.side_effect = [
            ModbusResponseError("device returned Modbus exception 2"), [6],
        ]
        results, errors = read_probe(self.session, report=self.messages.append)
        self.assertNotIn("AI filter", results)
        self.assertIn("exception 2", errors["AI filter"])
        self.assertEqual(results["DI filter"], [6])
        self.assertEqual(self.session.read_holding_registers.call_count, 2)
        self.assertIn("RESPONSE ERROR", self.messages[2])

    def test_transport_failure_aborts_without_retry_or_further_reads(self):
        self.session.read_discrete_inputs.side_effect = ModbusConnectionError("timeout")
        with self.assertRaisesRegex(ModbusConnectionError, "timeout"):
            read_probe(self.session, include_ai=True, report=self.messages.append)
        self.assertEqual(len(self.session.method_calls), 1)
        self.assertIn(ENDPOINT, self.messages[0])
        self.assertIn("remaining reads aborted", self.messages[0])


if __name__ == "__main__":
    unittest.main()
