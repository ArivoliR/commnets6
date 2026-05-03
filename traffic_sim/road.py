from collections import deque


class Road:
    def __init__(self, road_id: str, start: str, end: str,
                 capacity: int = 10, length: float = 1.0, speed_limit: float = 1.0):
        self.road_id = road_id
        self.start = start
        self.end = end
        self.capacity = capacity
        self.length = length
        self.speed_limit = speed_limit
        self.travel_time = max(1, int(length / speed_limit))

        self._in_transit: list = []   # [(vehicle, arrival_step), ...]
        self._queue: deque = deque()

        self.total_vehicles = 0
        self._queue_history: list = []

    @property
    def occupancy(self) -> int:
        return len(self._in_transit) + len(self._queue)

    def is_full(self) -> bool:
        return self.occupancy >= self.capacity

    def can_accept(self) -> bool:
        return not self.is_full()

    def admit_vehicle(self, vehicle, current_step: int) -> bool:
        if self.is_full():
            return False
        self._in_transit.append((vehicle, current_step + self.travel_time))
        vehicle.current_road = self.road_id
        self.total_vehicles += 1
        return True

    def step(self, current_step: int):
        self._queue_history.append(len(self._queue))
        still = []
        for vehicle, arrival in self._in_transit:
            if current_step >= arrival:
                self._queue.append(vehicle)
            else:
                still.append((vehicle, arrival))
        self._in_transit = still

    def peek_queue(self):
        return self._queue[0] if self._queue else None

    def dequeue_vehicle(self):
        return self._queue.popleft() if self._queue else None

    def queue_length(self) -> int:
        return len(self._queue)

    def avg_queue_length(self) -> float:
        if not self._queue_history:
            return 0.0
        return sum(self._queue_history) / len(self._queue_history)

    def __repr__(self):
        return f"Road({self.road_id}: {self.start}→{self.end}, cap={self.capacity})"
