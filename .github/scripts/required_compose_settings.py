"""Update the deployment inputs listed in .well-known from docker-compose.yml."""

import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


REQUIRED = re.compile(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?\?[^}]*)?\}")
PORT_DEFAULT = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-([0-9]+)\}")


def extract(compose: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return required Compose variables and numerically sorted host ports."""
    required = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            required.update(REQUIRED.findall(value))

    visit(compose)
    ports = set()
    for service in compose.get("services", {}).values():
        for mapping in service.get("ports", []):
            if isinstance(mapping, dict):
                host = str(mapping.get("published", ""))
                protocol = mapping.get("protocol", "tcp")
            else:
                mapping, _, protocol = str(mapping).partition("/")
                mapping = PORT_DEFAULT.sub(r"\1", mapping)
                host, separator, _ = mapping.rpartition(":")
                if not separator:
                    raise ValueError(f"port mapping has no fixed host port: {mapping}")
                host = host.rsplit(":", 1)[-1]
                protocol = protocol or "tcp"
            if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", host):
                raise ValueError(f"port mapping has no numeric host port: {mapping}")
            ports.add(host if protocol == "tcp" else f"{host}/{protocol}")
    return sorted(required), sorted(ports, key=lambda port: (int(port.split("-", 1)[0].split("/", 1)[0]), port))


def main() -> int:
    """Refresh the checked-in deployment lists."""
    required, ports = extract(yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8")))
    changed = False
    for name, values in (("required_env.txt", required), ("required_ports.txt", ports)):
        path = Path(".well-known") / name
        content = "\n".join(values) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.parent.mkdir(exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"Updated {path}; stage it and commit again")
            changed = True
    return int(changed)


if __name__ == "__main__":
    raise SystemExit(main())
