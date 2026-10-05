"""Small local HTTP host connecting the existing UI to the Python V5 solver."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from acs_load_calculator import LoadResult, calculate_40hc, calculate_pallet


HOST = "127.0.0.1"
PORT = 4173
DIST_DIRECTORY = Path(__file__).with_name("dist")


def _result_json(result: LoadResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "totalCartons": result.total_cartons,
        "cartonsPerLayer": result.cartons_per_layer,
        "layers": result.layers,
        "orientation": {
            "length": result.carton_length,
            "width": result.carton_width,
            "height": result.carton_height,
        },
        "loadedHeight": result.loaded_height,
        "floorUtilization": result.floor_utilization,
        "volumeUtilization": result.volume_utilization,
        "pattern": result.pattern_description,
        "solverStatus": result.solver_status,
        "placements": [
            {
                "x": placement.x,
                "y": placement.y,
                "length": placement.length,
                "width": placement.width,
            }
            for placement in result.placements
        ],
    }


class CalculatorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(DIST_DIRECTORY), **kwargs)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/api/calculate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            dimensions = tuple(int(payload[key]) for key in ("length", "width", "height"))
            if any(value <= 0 for value in dimensions):
                raise ValueError
            response = {
                "pallet": _result_json(calculate_pallet(*dimensions)),
                "container": _result_json(calculate_40hc(*dimensions)),
            }
            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400, "Dimensions must be positive whole millimetres")


def main() -> None:
    if not DIST_DIRECTORY.is_dir():
        raise SystemExit("Build the UI first with: npm run build")
    server = ThreadingHTTPServer((HOST, PORT), CalculatorHandler)
    print(f"ACS Load Calculator V5: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
