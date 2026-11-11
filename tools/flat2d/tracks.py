"""Timeline of a scene's states: each thing that changes (door, position, light, count) is a track
of segments (start, end, from, to) with smoothstep. A segment of duration 0 is a hard switch (logical state)."""

from .common import lerp, smooth


class Track:
    def __init__(self, value):
        self.start = value
        self.segs: list[tuple[float, float, object, object]] = []

    def at(self, t: float):
        v = self.start
        for t0, t1, a, b in self.segs:
            if t < t0:
                break
            v = b if t >= t1 or t1 <= t0 else lerp(a, b, smooth((t - t0) / (t1 - t0)))
        return v

    def to(self, t0: float, dur: float, value) -> None:
        """Goes from the value it has at t0 to 'value' over 'dur' seconds (events arrive in time order)."""
        self.segs.append((t0, t0 + max(0.0, dur), self.at(t0), value))

    def done(self, t: float) -> float:
        """Fraction (0..1, with easing) of the last segment already started; 1 when still."""
        last = None
        for seg in self.segs:
            if t >= seg[0]:
                last = seg
        if not last or last[1] <= last[0]:
            return 1.0
        return smooth((t - last[0]) / (last[1] - last[0]))
