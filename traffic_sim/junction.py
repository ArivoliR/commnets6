"""
Junction: an intersection node that connects multiple roads.

Supports 2-way, 3-way, and 4-way (and more) configurations.

Scheduling policy — max-pressure (improvements #2 + #3):
  Each step, serve the incoming road with the longest queue.
  This simultaneously:
    • skips empty lanes (improvement #2 — demand-driven)
    • prioritises the most congested lane (improvement #3 — max-pressure)
  Ties are broken by a round-robin pointer for fairness.
"""


class Junction:
    def __init__(self, junction_id: str, pos: tuple = (0.0, 0.0),
                 green_time: int = 1):
        self.junction_id = junction_id
        self.pos = pos
        self.green_time = green_time        # kept for API compat, unused by max-pressure

        self.incoming_roads: list = []
        self.outgoing_roads: list = []

        self._rr_ptr: int = 0               # round-robin tie-breaker
        self.vehicles_passed = 0

    def add_incoming(self, road_id: str):
        if road_id not in self.incoming_roads:
            self.incoming_roads.append(road_id)

    def add_outgoing(self, road_id: str):
        if road_id not in self.outgoing_roads:
            self.outgoing_roads.append(road_id)

    def ways(self) -> int:
        return max(len(self.incoming_roads), len(self.outgoing_roads))

    def step(self, roads: dict, current_step: int) -> list:
        """
        Max-pressure scheduling: serve the incoming road with the longest
        non-empty queue.  Ties broken by round-robin for starvation prevention.
        """
        forwarded = []
        if not self.incoming_roads:
            return forwarded

        n = len(self.incoming_roads)
        best_road_id = None
        best_q = 0
        # Scan starting from the RR pointer so ties are broken fairly
        for i in range(n):
            road_id = self.incoming_roads[(self._rr_ptr + i) % n]
            if road_id not in roads:
                continue
            q = roads[road_id].queue_length()
            if q > best_q:
                best_q = q
                best_road_id = road_id

        # Always advance RR pointer (fairness when queues are equal)
        self._rr_ptr = (self._rr_ptr + 1) % n

        if best_road_id is None or best_q == 0:
            return forwarded           # all queues empty — nothing to do

        road = roads[best_road_id]
        vehicle = road.peek_queue()
        if vehicle is None:
            return forwarded

        next_node = vehicle.next_node
        if next_node is None:
            road.dequeue_vehicle()
            return forwarded

        target_road = self._find_outgoing_road(next_node, roads)
        if target_road is None:
            return forwarded

        if target_road.can_accept():
            road.dequeue_vehicle()
            vehicle.advance_route()
            target_road.admit_vehicle(vehicle, current_step)
            self.vehicles_passed += 1
            forwarded.append(vehicle)

        return forwarded

    def _find_outgoing_road(self, target_node_id: str, roads: dict):
        for road_id in self.outgoing_roads:
            if road_id in roads and roads[road_id].end == target_node_id:
                return roads[road_id]
        return None

    def __repr__(self):
        return (f"Junction({self.junction_id}, {self.ways()}-way, "
                f"in={self.incoming_roads}, out={self.outgoing_roads})")
