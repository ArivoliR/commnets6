from collections import deque

_vehicle_counter = 0

def _next_id():
    global _vehicle_counter
    _vehicle_counter += 1
    return _vehicle_counter


class Vehicle:
    def __init__(self, source: str, destination: str, spawn_step: int,
                 color: str = "#FF5733"):
        self.vehicle_id = _next_id()
        self.source = source
        self.destination = destination
        self.spawn_step = spawn_step
        self.color = color

        self.route: list = []
        self.route_index: int = 0
        self.current_road: str = None
        self.current_node: str = source
        self.arrival_step: int = None
        self.total_wait: int = 0

    @property
    def next_node(self) -> str:
        if self.route_index < len(self.route):
            return self.route[self.route_index]
        return None

    def advance_route(self):
        self.route_index += 1
        if self.route_index < len(self.route):
            self.current_node = self.route[self.route_index - 1]

    def has_arrived(self) -> bool:
        return self.route_index >= len(self.route)

    def __repr__(self):
        return f"Vehicle({self.vehicle_id}: {self.source}→{self.destination})"
