import heapq


class Router:
    def __init__(self, roads: dict):
        self._graph: dict = {}
        for road in roads.values():
            self._graph.setdefault(road.start, [])
            self._graph.setdefault(road.end, [])
            self._graph[road.start].append((road.travel_time, road.road_id, road.end))

    def shortest_path(self, source: str, destination: str) -> list:
        if source == destination:
            return [source]

        dist = {source: 0}
        prev = {}
        heap = [(0, source)]

        while heap:
            cost, node = heapq.heappop(heap)
            if cost > dist.get(node, float("inf")):
                continue
            if node == destination:
                break
            for edge_cost, _, neighbour in self._graph.get(node, []):
                new_cost = cost + edge_cost
                if new_cost < dist.get(neighbour, float("inf")):
                    dist[neighbour] = new_cost
                    prev[neighbour] = node
                    heapq.heappush(heap, (new_cost, neighbour))

        if destination not in prev and destination != source:
            return []

        path, node = [], destination
        while node != source:
            path.append(node)
            node = prev[node]
        path.append(source)
        path.reverse()
        return path

    def route_vehicle(self, vehicle, source: str, destination: str) -> bool:
        path = self.shortest_path(source, destination)
        if not path:
            return False
        vehicle.route = path
        vehicle.route_index = 1
        return True
