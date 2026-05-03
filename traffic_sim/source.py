"""
TrafficSource: generates vehicles at a junction or dedicated source node.

Improvement #1 — source queue:
  Generated vehicles are held in a waiting deque and injected onto their
  first road only when capacity is available.  No vehicle is ever silently
  dropped; every Poisson-sampled vehicle eventually enters the network.
  Vehicles with different first roads are tried independently, so a
  blocked road only stalls its own queue.
"""
import random
import math
from collections import deque


class TrafficSource:
    def __init__(self, source_id: str, node_id: str, destinations: list,
                 rate: float = 0.5, mode: str = "poisson",
                 dest_colors: dict = None):
        self.source_id = source_id
        self.node_id = node_id
        self.destinations = destinations
        self.rate = rate
        self.mode = mode
        self.dest_colors = dest_colors or {}

        self._accumulator = 0.0
        self._waiting: deque = deque()   # routed vehicles waiting for road space
        self.total_generated = 0         # vehicles created by Poisson/constant
        self.total_spawned = 0           # vehicles that actually entered the network

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, current_step: int) -> int:
        if self.mode == "constant":
            self._accumulator += self.rate
            count = int(self._accumulator)
            self._accumulator -= count
            return count
        elif self.mode == "poisson":
            return self._poisson_sample(self.rate)
        return 0

    def enqueue(self, vehicle):
        """Add a fully-routed vehicle to the waiting queue."""
        self._waiting.append(vehicle)
        self.total_generated += 1

    # ------------------------------------------------------------------
    # Injection (called every step by the engine)
    # ------------------------------------------------------------------

    def try_inject(self, find_road_fn, active_vehicles: list,
                   all_vehicles: list, step: int):
        """
        Push as many waiting vehicles as possible onto the network.
        Vehicles with different first roads are tried independently.
        """
        remaining = deque()
        while self._waiting:
            vehicle = self._waiting.popleft()
            first_road = find_road_fn(self.node_id, vehicle.next_node)
            if first_road and first_road.can_accept():
                first_road.admit_vehicle(vehicle, step)
                vehicle.advance_route()
                active_vehicles.append(vehicle)
                all_vehicles.append(vehicle)
                self.total_spawned += 1
            else:
                remaining.append(vehicle)
        self._waiting = remaining

    @property
    def waiting_count(self) -> int:
        return len(self._waiting)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _poisson_sample(lam: float) -> int:
        if lam <= 0:
            return 0
        L = math.exp(-lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1

    def pick_destination(self) -> str:
        return random.choice(self.destinations)

    def color_for(self, destination: str) -> str:
        return self.dest_colors.get(destination, "#AAAAAA")

    def __repr__(self):
        return (f"TrafficSource({self.source_id} @ {self.node_id}, "
                f"rate={self.rate}, waiting={self.waiting_count})")
