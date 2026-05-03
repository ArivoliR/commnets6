import random
from traffic_sim import Road, Junction, TrafficSource, Sink, SimulationEngine
from traffic_sim.visualizer import Visualizer

SIM_STEPS     = 300
RECORD_EVERY  = 2
ANIMATION_FPS = 10
ROAD_CAP      = 8
ROAD_LEN      = 3
GREEN_TIME    = 1

RATE_S1S4 = 0.38
RATE_S2S5 = 0.38
RATE_S3   = 0.30

NODE_POS = {
    "SRC_S1S4": (-1.5, 6.0), "SRC_S2S5": (-1.5, 3.0), "SRC_S3":    ( 7.5, 3.0),
    "J00": (0.0, 6.0), "J10": (3.0, 6.0), "J20": (6.0, 6.0),
    "J01": (0.0, 3.0), "J11": (3.0, 3.0), "J21": (6.0, 3.0),
    "J02": (0.0, 0.0), "J12": (3.0, 0.0), "J22": (6.0, 0.0),
    "SINK_K2": (7.5, 6.0), "SINK_K1K5": (7.5, 0.0), "SINK_K3K4": (-1.5, 0.0),
}

NODE_TYPES = {
    "SRC_S1S4": "source", "SRC_S2S5": "source", "SRC_S3": "source",
    "J00": "junction", "J10": "junction", "J20": "junction",
    "J01": "junction", "J11": "junction", "J21": "junction",
    "J02": "junction", "J12": "junction", "J22": "junction",
    "SINK_K2": "sink", "SINK_K1K5": "sink", "SINK_K3K4": "sink",
}

# separate colour table per source so S1 and S5 (same sink, different source) get different colours
DEST_COLORS_S1S4 = {"SINK_K1K5": "#e63946", "SINK_K3K4": "#f4a261"}
DEST_COLORS_S2S5 = {"SINK_K2":   "#4895ef", "SINK_K1K5": "#9b5de5"}
DEST_COLORS_S3   = {"SINK_K3K4": "#2dc653"}

LEGEND_COLORS = {
    "S1 → SINK_K1K5": "#e63946",
    "S4 → SINK_K3K4": "#f4a261",
    "S2 → SINK_K2":   "#4895ef",
    "S5 → SINK_K1K5": "#9b5de5",
    "S3 → SINK_K3K4": "#2dc653",
}


def build_network() -> SimulationEngine:
    engine = SimulationEngine()

    for jid in ("J00","J10","J20","J01","J11","J21","J02","J12","J22"):
        engine.add_junction(Junction(jid, NODE_POS[jid], green_time=GREEN_TIME))

    engine.add_sink(Sink("SINK_K2",   NODE_POS["SINK_K2"]))
    engine.add_sink(Sink("SINK_K1K5", NODE_POS["SINK_K1K5"]))
    engine.add_sink(Sink("SINK_K3K4", NODE_POS["SINK_K3K4"]))

    def road(rid, start, end, cap=ROAD_CAP, length=ROAD_LEN):
        engine.add_road(Road(rid, start, end, capacity=cap, length=length, speed_limit=1))

    road("R_src_s1s4_J00", "SRC_S1S4", "J00", cap=30, length=1)
    road("R_src_s2s5_J01", "SRC_S2S5", "J01", cap=30, length=1)
    road("R_src_s3_J21",   "SRC_S3",   "J21", cap=30, length=1)
    road("R_J20_snk_k2",   "J20", "SINK_K2",   cap=30, length=1)
    road("R_J22_snk_k1k5", "J22", "SINK_K1K5", cap=30, length=1)
    road("R_J02_snk_k3k4", "J02", "SINK_K3K4", cap=30, length=1)

    road("R_J00_J10","J00","J10"); road("R_J10_J00","J10","J00")
    road("R_J10_J20","J10","J20"); road("R_J20_J10","J20","J10")
    road("R_J01_J11","J01","J11"); road("R_J11_J01","J11","J01")
    road("R_J11_J21","J11","J21"); road("R_J21_J11","J21","J11")
    road("R_J02_J12","J02","J12"); road("R_J12_J02","J12","J02")
    road("R_J12_J22","J12","J22"); road("R_J22_J12","J22","J12")
    road("R_J00_J01","J00","J01"); road("R_J01_J00","J01","J00")
    road("R_J01_J02","J01","J02"); road("R_J02_J01","J02","J01")
    road("R_J10_J11","J10","J11"); road("R_J11_J10","J11","J10")
    road("R_J11_J12","J11","J12"); road("R_J12_J11","J12","J11")
    road("R_J20_J21","J20","J21"); road("R_J21_J20","J21","J20")
    road("R_J21_J22","J21","J22"); road("R_J22_J21","J22","J21")

    engine.add_source(TrafficSource("SRC_S1S4", "SRC_S1S4",
        ["SINK_K1K5", "SINK_K3K4"], RATE_S1S4, "poisson", DEST_COLORS_S1S4))
    engine.add_source(TrafficSource("SRC_S2S5", "SRC_S2S5",
        ["SINK_K2", "SINK_K1K5"],   RATE_S2S5, "poisson", DEST_COLORS_S2S5))
    engine.add_source(TrafficSource("SRC_S3", "SRC_S3",
        ["SINK_K3K4"],              RATE_S3,   "poisson", DEST_COLORS_S3))

    engine.build()
    return engine


def print_stats(stats):
    print("\n" + "═" * 55)
    print("  3×3 Grid Traffic Simulation — Results")
    print("═" * 55)
    gen = stats.get("total_generated", stats["total_spawned"])
    print(f"  Steps            : {stats['total_steps']}")
    print(f"  Generated        : {gen}")
    print(f"  Spawned          : {stats['total_spawned']}")
    print(f"  Absorbed         : {stats['total_absorbed']}")
    print(f"  In network       : {stats['vehicles_in_network']}")
    print(f"  Waiting          : {stats.get('vehicles_waiting', 0)}")
    print(f"  Avg travel time  : {stats['avg_travel_time']:.1f} steps")
    print(f"  Min/Max travel   : {stats['min_travel_time']} / {stats['max_travel_time']}")
    print(f"  Avg queue        : {stats['avg_queue_length']:.2f}")
    print(f"  Peak queue       : {stats['peak_queue_length']}")
    print("\n  Per sink:")
    for sid, s in stats["per_sink"].items():
        print(f"    {sid:12s}  absorbed={s['absorbed']:4d}  avg_travel={s['avg_travel_time']:.1f}")
    print("\n  Per junction:")
    for jid, j in stats["per_junction"].items():
        print(f"    {jid} ({j['ways']}-way)  forwarded={j['vehicles_passed']}")
    print("═" * 55 + "\n")


def save_stats(stats, path):
    lines = ["3x3 Grid Traffic Simulation — Assignment 6", "=" * 50]
    for k, v in stats.items():
        if k in ("throughput_per_step","queue_per_step","per_sink","per_road","per_junction"):
            continue
        lines.append(f"{k}: {v}")
    lines.append("\nPer sink:")
    for sid, s in stats["per_sink"].items():
        lines.append(f"  {sid}: absorbed={s['absorbed']}, avg_travel={s['avg_travel_time']:.2f}")
    lines.append("\nPer junction:")
    for jid, j in stats["per_junction"].items():
        lines.append(f"  {jid} ({j['ways']}-way): {j['vehicles_passed']} forwarded")
    lines.append("\nPer road:")
    for rid, r in stats["per_road"].items():
        lines.append(f"  {rid}: total={r['total_vehicles']}, avg_queue={r['avg_queue']:.2f}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Statistics → {path}")


if __name__ == "__main__":
    random.seed(42)

    engine = build_network()
    print(f"Network: {len(engine.junctions)} junctions, {len(engine.roads)} roads")

    engine.run(steps=SIM_STEPS, record_every=RECORD_EVERY)

    stats = engine.statistics()
    print_stats(stats)
    save_stats(stats, "statistics.txt")

    viz = Visualizer(engine, NODE_POS, NODE_TYPES, LEGEND_COLORS,
                     title="3×3 Grid Traffic Simulator — Assignment 6")
    viz.animate("simulation.gif", fps=ANIMATION_FPS)
    viz.plot_statistics(stats, "statistics.png")
    print("Outputs: simulation.gif  statistics.png  statistics.txt")
