"""
MudClient — persistent socket connection to tbaMUD.

Simple send/sleep/drain pattern. Login flow for tbaMUD is:
  name -> password -> "*** PRESS RETURN" -> menu -> "1" -> in game
"""

from __future__ import annotations

import re
import socket
import time

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_TELNET = re.compile(rb"\xff[\xfa-\xff][\x00-\xff]?")


def _clean(raw: bytes) -> str:
    raw = _TELNET.sub(b"", raw)
    return _ANSI.sub("", raw.decode("utf-8", errors="replace"))


class MudClient:
    def __init__(self, host: str = "localhost", port: int = 4000, wait: float = 1.0):
        self.host = host
        self.port = port
        self.wait = wait
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(0.5)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.sendall(b"quit\r\n")
                time.sleep(0.3)
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def _drain(self, wait: float | None = None) -> str:
        assert self.sock is not None
        time.sleep(wait if wait is not None else self.wait)
        chunks: list[bytes] = []
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        except socket.timeout:
            pass
        return _clean(b"".join(chunks))

    def _send(self, text: str) -> None:
        assert self.sock is not None
        self.sock.sendall((text + "\r\n").encode("utf-8"))

    def login(self, name: str, password: str) -> str:
        if self.sock is None:
            self.connect()

        transcript = []
        transcript.append(self._drain(1.5))          # greeting + name prompt

        self._send(name)
        resp = self._drain(1.0)
        transcript.append(resp)
        if "did i get that right" in resp.lower():
            raise RuntimeError(f"'{name}' doesn't exist — MUD wants to create it.")

        self._send(password)
        resp = self._drain(1.5)                        # PRESS RETURN and/or MOTD
        transcript.append(resp)

        # Keep pressing RETURN until we see the menu, then choose 1.
        for _ in range(4):
            low = resp.lower()
            if "make your choice" in low or "enter the game" in low:
                break
            self._send("")                             # hit RETURN
            resp = self._drain(1.0)
            transcript.append(resp)

        # Now we should be at the menu — choose 1 to enter the game.
        self._send("1")
        resp = self._drain(1.5)
        transcript.append(resp)

        return "\n".join(s for s in transcript if s.strip())

    def send(self, command: str) -> str:
        if self.sock is None:
            raise RuntimeError("not connected — call login() first")
        self._send(command)
        return self._drain().strip()


if __name__ == "__main__":
    mud = MudClient()
    print("=== LOGIN ===")
    print(mud.login("dummy", "helloworld"))

    print("\n=== look ===")
    print(mud.send("look"))

    print("\n=== exits ===")
    print(mud.send("exits"))

    print("\n=== score ===")
    print(mud.send("score"))

    mud.close()
    print("\n(closed)")