"""Base definitions and abstract interface for PipeVision Robot Transport."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class TransportError(Exception):
    """Base exception for all robot transport errors."""


class TransportNotConnectedError(TransportError):
    """Raised when performing transport operations while disconnected."""


class TransportConnectionError(TransportError):
    """Raised when establishing or communicating over a transport connection fails."""


class InvalidMessageError(TransportError):
    """Raised when a message format or payload violates protocol specifications."""


COMMANDS_JSON_PATH = Path(__file__).parent.parent / "protocol" / "commands.json"


def load_command_protocol(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load command definitions from commands.json.

    Returns dict mapping command_name -> dict of argument_name -> type_string.
    """
    filepath = path or COMMANDS_JSON_PATH
    if not filepath.exists():
        return {}

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        commands: dict[str, dict[str, str]] = {}
        for cmd in data.get("commands", []):
            commands[cmd["name"]] = cmd.get("arguments", {})
        return commands
    except Exception as err:
        raise InvalidMessageError(f"Failed to load command protocol: {err}") from err


def validate_command_dict(
    command_dict: dict[str, Any],
    valid_commands: dict[str, dict[str, str]] | None = None,
) -> None:
    """Validate a command dictionary against commands.json protocol schema."""
    if not isinstance(command_dict, dict):
        raise InvalidMessageError("Command message must be a dictionary.")

    name = command_dict.get("name")
    if not name or not isinstance(name, str):
        raise InvalidMessageError("Command must contain a string 'name'.")

    protocol = valid_commands if valid_commands is not None else load_command_protocol()
    if protocol and name not in protocol:
        raise InvalidMessageError(f"Unknown command name: '{name}'")

    if protocol:
        expected_args = protocol[name]
        provided_args = command_dict.get("arguments", {})
        if provided_args is None:
            provided_args = {}

        if not isinstance(provided_args, dict):
            raise InvalidMessageError("Command 'arguments' must be a dictionary.")

        for arg_name, arg_type in expected_args.items():
            if arg_name not in provided_args:
                raise InvalidMessageError(
                    f"Command '{name}' missing required argument '{arg_name}'."
                )

            val = provided_args[arg_name]
            if arg_type in ("float", "int"):
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    raise InvalidMessageError(
                        f"Command '{name}' argument '{arg_name}' expected {arg_type}, got {type(val).__name__}."
                    )
            elif arg_type == "string" and not isinstance(val, str):
                raise InvalidMessageError(
                    f"Command '{name}' argument '{arg_name}' expected string, got {type(val).__name__}."
                )


class RobotTransport(ABC):
    """Abstract interface for robot physical and simulated transport connections."""

    @abstractmethod
    def connect(self) -> None:
        """Establish transport connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect transport connection cleanly."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if connection is active."""

    @abstractmethod
    def send(self, message: dict[str, Any] | str) -> None:
        """Send a command or message over the transport."""

    @abstractmethod
    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        """Receive a telemetry packet or message over the transport.

        Returns None if timeout expires before a message arrives.
        """
