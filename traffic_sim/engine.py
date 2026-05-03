"""
SimulationEngine: the core time-step based discrete-event simulator.

Step order each tick
--------------------
1. Generate new vehicles → enqueue in source waiting queues.
2. Try to inject from source queues onto first roads (no drops).
3. Roads advance: transit → junction queue when travel time expires.
4. Sinks absorb vehicles from incoming road queues.
5. Junctions forward vehicles (max-pressure scheduling).
6. Collect stats + snapshot.
"""
from .road import Road
from .junction import Junction
from .source import TrafficSource
from .sink import Sink
from .vehicle import Vehicle
from .router import Router


class SimulationEngine:
    def __init__(self):
        self.roads: dict = {}
        self.junctions: dict = {}
        self.sources: dict = {}
        self.sinks: dict = {}

        self._router: Router = None
        self._active_vehicles: list = []
        self._all_vehicles: list = []

        self.current_step: int = 0
        self.frames: list = []

        self._throughput_per_step: list = []
        self._queue_per_step: list = []

    def add_road(self, road: Road):
        self.roads[road.road_id] = road

    def add_junction(self, junction: Junction):
        self.junctions[junction.junction_id] = junction

    def add_source(self, source: TrafficSource):
        self.sources[source.source_id] = source

    def add_sink(self, sink: Sink):
        self.sinks[sink.sink_id] = sink

    def build(self):
        for road_id, road in self.roads.items():
            if road.start in self.junctions:
                self.junctions[road.start].add_outgoing(road_id)
            if road.end in self.junctions:
                self.junctions[road.end].add_incoming(road_id)
            if road.end in self.sinks:
                self.sinks[road.end].add_incoming(road_id)
        self._router = Router(self.roads)

    def run(self, steps: int = 200, record_every: int = 1):
        for step in range(steps):
            self.current_step = step
            absorbed = self._step(step)
            self._throughput_per_step.append(len(absorbed))
            total_q = sum(r.queue_length() for r in self.roads.values())
            self._queue_per_step.append(total_q)
            if step % record_every == 0:
                self.frames.append(self._snapshot(step))
        self.frames.append(self._snapshot(steps))

    def _step(self, step: int) -> list:
        # 1. Generate → source queues (no vehicle is ever dropped)
        for source in self.sources.values():
            count = source.generate(step)
            for _ in range(count):
                dest = source.pick_destination()
                color = source.color_for(dest)
                vehicle = Vehicle(source.node_id, dest, step, color)
                if self._router.route_vehicle(vehicle, source.node_id, dest):
                    source.enqueue(vehicle)

        # 2. Inject from source queues onto first roads
        for source in self.sources.values():
            source.try_inject(self._find_first_road,
                              self._active_vehicles, self._all_vehicles, step)

        # 3. Roads advance (transit → queue)
        for road in self.roads.values():
            road.step(step)

        # 4. Sinks absorb
        absorbed = []
        for sink in self.sinks.values():
            absorbed.extend(sink.step(self.roads, step))

        # 5. Junctions forward (max-pressure)
        for junction in self.junctions.values():
            junction.step(self.roads, step)

        # 6. Prune active list
        absorbed_ids = {v.vehicle_id for v in absorbed}
        self._active_vehicles = [v for v in self._active_vehicles
                                  if v.vehicle_id not in absorbed_ids]
        return absorbed

    def _find_first_road(self, from_node: str, to_node: str):
        for road in self.roads.values():
            if road.start == from_node and road.end == to_node:
                return road
        return None

    def _snapshot(self, step: int) -> dict:
        vehicle_positions = []
        for road in self.roads.values():
            for vehicle, arrival in road._in_transit:
                progress = 1.0 - max(0, arrival - step) / max(1, road.travel_time)
                vehicle_positions.append({
                    "id": vehicle.vehicle_id,
                    "road": road.road_id,
                    "progress": min(1.0, progress),
                    "color": vehicle.color,
                    "source": vehicle.source,
                    "dest": vehicle.destination,
                    "in_queue": False,
                })
            for i, vehicle in enumerate(road._queue):
                vehicle_positions.append({
                    "id": vehicle.vehicle_id,
                    "road": road.road_id,
                    "progress": 1.0,
                    "color": vehicle.color,
                    "source": vehicle.source,
                    "dest": vehicle.destination,
                    "in_queue": True,
                    "queue_pos": i,
                })

        road_queues = {rid: r.queue_length() for rid, r in self.roads.items()}
        road_occupancy = {rid: r.occupancy for rid, r in self.roads.items()}
        total_absorbed = sum(s.throughput for s in self.sinks.values())
        per_sink_absorbed = {sid: s.throughput for sid, s in self.sinks.items()}

        return {
            "step": step,
            "vehicles": vehicle_positions,
            "road_queues": road_queues,
            "road_occupancy": road_occupancy,
            "active_count": len(self._active_vehicles),
            "total_absorbed": total_absorbed,
            "per_sink_absorbed": per_sink_absorbed,
        }

    def statistics(self) -> dict:
        all_travel = []
        for sink in self.sinks.values():
            all_travel.extend(sink.total_travel_times)

        total_generated = sum(s.total_generated for s in self.sources.values())
        total_spawned   = sum(s.total_spawned   for s in self.sources.values())
        total_waiting   = sum(s.waiting_count   for s in self.sources.values())
        total_absorbed  = sum(s.throughput      for s in self.sinks.values())

        return {
            "total_steps":          self.current_step + 1,
            "total_generated":      total_generated,
            "total_spawned":        total_spawned,
            "total_absorbed":       total_absorbed,
            "vehicles_in_network":  total_spawned - total_absorbed,
            "vehicles_waiting":     total_waiting,
            "avg_travel_time":      sum(all_travel) / len(all_travel) if all_travel else 0,
            "min_travel_time":      min(all_travel) if all_travel else 0,
            "max_travel_time":      max(all_travel) if all_travel else 0,
            "avg_queue_length":     (sum(self._queue_per_step) / len(self._queue_per_step)
                                     if self._queue_per_step else 0),
            "peak_queue_length":    max(self._queue_per_step) if self._queue_per_step else 0,
            "throughput_per_step":  self._throughput_per_step,
            "queue_per_step":       self._queue_per_step,
            "per_sink": {
                sid: {"absorbed": s.throughput, "avg_travel_time": s.avg_travel_time()}
                for sid, s in self.sinks.items()
            },
            "per_road": {
                rid: {"total_vehicles": r.total_vehicles, "avg_queue": r.avg_queue_length()}
                for rid, r in self.roads.items()
            },
            "per_junction": {
                jid: {"vehicles_passed": j.vehicles_passed, "ways": j.ways()}
                for jid, j in self.junctions.items()
            },
        }
