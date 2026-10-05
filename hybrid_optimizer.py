"""Symmetry-reduced CP-SAT layer optimization for the V5 calculator."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Sequence

from ortools.sat.python import cp_model


CP_SAT_TIME_LIMIT = 8.0
CP_SAT_WORKERS = 8
DIRECT_CARTON_LIMIT = 60
FRINGE_CARTON_LIMIT = 35
IDEAL_FRINGE_CARTONS = 24
MIN_FRINGE_DENSITY = 0.975


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    length: int
    width: int


@dataclass(frozen=True)
class LayerSolution:
    count: int
    pattern: str
    placements: tuple[Placement, ...] = ()
    status: str = "FAST"


@dataclass(frozen=True)
class StripPattern:
    row_counts: tuple[int, ...]
    columns: tuple[int, ...]
    orientations: tuple[tuple[int, int], ...]
    count: int


def placements_are_valid(
    placements: Sequence[Placement], area_length: int, area_width: int
) -> bool:
    """Validate bounds and every pairwise non-overlap using integer geometry."""

    for index, rectangle in enumerate(placements):
        if (
            rectangle.x < 0
            or rectangle.y < 0
            or rectangle.x + rectangle.length > area_length
            or rectangle.y + rectangle.width > area_width
        ):
            return False
        for other in placements[index + 1 :]:
            if not (
                rectangle.x + rectangle.length <= other.x
                or other.x + other.length <= rectangle.x
                or rectangle.y + rectangle.width <= other.y
                or other.y + other.width <= rectangle.y
            ):
                return False
    return True


def _normal_coordinates(limit: int, first: int, second: int) -> list[int]:
    """Safe start coordinates for a bottom/left-compacted unobstructed packing."""

    return sorted(
        {
            first_count * first + second_count * second
            for first_count in range(limit // first + 1)
            for second_count in range(limit // second + 1)
            if first_count * first + second_count * second <= limit
        }
    )


def _solve_exact(
    area_length: int,
    area_width: int,
    carton_length: int,
    carton_width: int,
    target: int,
    seconds: float,
    obstacles: Sequence[Placement] = (),
    x_offset: int = 0,
) -> tuple[str, tuple[Placement, ...]]:
    """Ask CP-SAT for a target count and return only a revalidated layout."""

    if target <= 0 or seconds <= 0.05:
        return "UNKNOWN", ()

    model = cp_model.CpModel()
    x_intervals = []
    y_intervals = []
    x_demands = []
    y_demands = []
    xs = []
    ys = []
    rotations = []
    same_sides = carton_length == carton_width

    if obstacles:
        x_domain = y_domain = None
    else:
        x_domain = cp_model.Domain.from_values(
            _normal_coordinates(area_length, carton_length, carton_width)
        )
        y_domain = cp_model.Domain.from_values(
            _normal_coordinates(area_width, carton_length, carton_width)
        )

    for index in range(target):
        x = (
            model.new_int_var_from_domain(x_domain, f"x{index}")
            if x_domain is not None
            else model.new_int_var(0, area_length - min(carton_length, carton_width), f"x{index}")
        )
        y = (
            model.new_int_var_from_domain(y_domain, f"y{index}")
            if y_domain is not None
            else model.new_int_var(0, area_width - min(carton_length, carton_width), f"y{index}")
        )
        if same_sides:
            rotation = model.new_constant(0)
            length = carton_length
            width = carton_width
        else:
            rotation = model.new_bool_var(f"r{index}")
            length = model.new_int_var(
                min(carton_length, carton_width),
                max(carton_length, carton_width),
                f"l{index}",
            )
            width = model.new_int_var(
                min(carton_length, carton_width),
                max(carton_length, carton_width),
                f"w{index}",
            )
            model.add(length == carton_length + (carton_width - carton_length) * rotation)
            model.add(width == carton_width + (carton_length - carton_width) * rotation)

        x_end = model.new_int_var(0, area_length, f"xe{index}")
        y_end = model.new_int_var(0, area_width, f"ye{index}")
        model.add(x_end == x + length)
        model.add(y_end == y + width)
        x_intervals.append(model.new_interval_var(x, length, x_end, f"xi{index}"))
        y_intervals.append(model.new_interval_var(y, width, y_end, f"yi{index}"))
        x_demands.append(width)
        y_demands.append(length)
        xs.append(x)
        ys.append(y)
        rotations.append(rotation)

    for index, obstacle in enumerate(obstacles):
        x_intervals.append(
            model.new_fixed_size_interval_var(obstacle.x, obstacle.length, f"oxi{index}")
        )
        y_intervals.append(
            model.new_fixed_size_interval_var(obstacle.y, obstacle.width, f"oyi{index}")
        )
        x_demands.append(obstacle.width)
        y_demands.append(obstacle.length)

    model.add_no_overlap_2d(x_intervals, y_intervals)
    model.add_cumulative(x_intervals, x_demands, area_width)
    model.add_cumulative(y_intervals, y_demands, area_length)

    # Identical rectangles can always be relabelled in this order.  This safe
    # symmetry break removes the factorial permutation symmetry.
    for index in range(target - 1):
        model.add(
            xs[index] * (area_width + 1) + ys[index]
            < xs[index + 1] * (area_width + 1) + ys[index + 1]
        )
    if not obstacles:
        model.add(xs[0] == 0)
        model.add_min_equality(0, ys)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = CP_SAT_WORKERS
    solver.parameters.random_seed = 0
    solver.parameters.use_energetic_reasoning_in_no_overlap_2d = True
    solver.parameters.use_timetabling_in_no_overlap_2d = True
    solver.parameters.use_try_edge_reasoning_in_no_overlap_2d = True
    status_code = solver.solve(model)
    status = solver.status_name(status_code)
    if status_code not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return status, ()

    placements = tuple(
        Placement(
            x=x_offset + solver.value(xs[index]),
            y=solver.value(ys[index]),
            length=carton_width if solver.value(rotations[index]) else carton_length,
            width=carton_length if solver.value(rotations[index]) else carton_width,
        )
        for index in range(target)
    )
    local = tuple(
        Placement(p.x - x_offset, p.y, p.length, p.width) for p in placements
    )
    if not placements_are_valid((*local, *obstacles), area_length, area_width):
        return "INVALID", ()
    return status, placements


def _best_strip(
    area_length: int, area_width: int, carton_length: int, carton_width: int
) -> StripPattern:
    orientations = [(carton_length, carton_width)]
    if carton_length != carton_width:
        orientations.append((carton_width, carton_length))
    if len(orientations) == 1:
        length, width = orientations[0]
        rows = area_width // width
        columns = area_length // length
        return StripPattern((rows,), (columns,), tuple(orientations), rows * columns)

    first, second = orientations
    best = StripPattern((0, 0), (0, 0), tuple(orientations), 0)
    for first_rows in range(area_width // first[1] + 1):
        second_rows = (area_width - first_rows * first[1]) // second[1]
        columns = (area_length // first[0], area_length // second[0])
        count = first_rows * columns[0] + second_rows * columns[1]
        if count > best.count:
            best = StripPattern((first_rows, second_rows), columns, tuple(orientations), count)
    return best


def _fringe_candidates(strip: StripPattern, target: int) -> list[tuple[int, ...]]:
    ranges = [range(max(0, columns - 8), columns + 1) for columns in strip.columns]
    combinations = (
        ((value,) for value in ranges[0])
        if len(ranges) == 1
        else ((first, second) for first in ranges[0] for second in ranges[1])
    )
    scored = []
    for frozen_columns in combinations:
        frozen_count = sum(
            rows * columns for rows, columns in zip(strip.row_counts, frozen_columns)
        )
        active = target - frozen_count
        if not 0 < active <= FRINGE_CARTON_LIMIT:
            continue
        ends = [
            columns * orientation[0]
            for rows, columns, orientation in zip(
                strip.row_counts, frozen_columns, strip.orientations
            )
            if rows and columns
        ]
        if ends:
            score = (abs(active - IDEAL_FRINGE_CARTONS), max(ends) - min(ends), -min(ends))
            scored.append((score, tuple(frozen_columns)))
    return [candidate for _, candidate in sorted(scored)]


def _frozen_prefix(
    strip: StripPattern, frozen_columns: Sequence[int]
) -> tuple[tuple[Placement, ...], tuple[Placement, ...], int]:
    ends = [
        columns * orientation[0]
        for rows, columns, orientation in zip(
            strip.row_counts, frozen_columns, strip.orientations
        )
        if rows and columns
    ]
    if not ends:
        return (), (), 0
    origin = min(ends)
    frozen = []
    obstacles = []
    y = 0
    for rows, columns, (length, width) in zip(
        strip.row_counts, frozen_columns, strip.orientations
    ):
        for row in range(rows):
            frozen.extend(
                Placement(column * length, y + row * width, length, width)
                for column in range(columns)
            )
        end = columns * length
        if rows and end > origin:
            obstacles.append(Placement(0, y, end - origin, rows * width))
        y += rows * width
    return tuple(frozen), tuple(obstacles), origin


def solve_hybrid_layer(
    area_length: int,
    area_width: int,
    carton_length: int,
    carton_width: int,
    base_count: int,
    base_pattern: str,
) -> LayerSolution:
    """Improve the supplied fast lower bound without ever losing it."""

    baseline = LayerSolution(base_count, base_pattern)
    carton_area = carton_length * carton_width
    if carton_area <= 0:
        return baseline
    area_upper_bound = area_length * area_width // carton_area
    if base_count >= area_upper_bound:
        return LayerSolution(base_count, base_pattern, status="AREA_OPTIMAL")

    deadline = monotonic() + CP_SAT_TIME_LIMIT
    if area_upper_bound <= DIRECT_CARTON_LIMIT:
        best = baseline
        for target in range(base_count + 1, area_upper_bound + 1):
            status, placements = _solve_exact(
                area_length,
                area_width,
                carton_length,
                carton_width,
                target,
                deadline - monotonic(),
            )
            if status in ("FEASIBLE", "OPTIMAL"):
                best = LayerSolution(
                    target,
                    f"CP-SAT interlocking pattern ({target} cartons)",
                    placements,
                    status,
                )
            else:
                break
        return best

    strip = _best_strip(area_length, area_width, carton_length, carton_width)
    # Fringe CP-SAT is most valuable for the dense +1 misses seen in long
    # containers.  Looser layers create much larger, low-value searches.
    if strip.count != base_count or base_count / area_upper_bound < MIN_FRINGE_DENSITY:
        return baseline

    target = base_count + 1
    for frozen_columns in _fringe_candidates(strip, target)[:4]:
        remaining = deadline - monotonic()
        if remaining <= 0.05:
            break
        frozen, obstacles, origin = _frozen_prefix(strip, frozen_columns)
        status, active = _solve_exact(
            area_length - origin,
            area_width,
            carton_length,
            carton_width,
            target - len(frozen),
            remaining,
            obstacles,
            origin,
        )
        if status in ("FEASIBLE", "OPTIMAL"):
            placements = (*frozen, *active)
            if placements_are_valid(placements, area_length, area_width):
                return LayerSolution(
                    target,
                    f"CP-SAT interlocking strip/fringe pattern ({target} cartons)",
                    placements,
                    status,
                )
        if status == "UNKNOWN":
            break
    return baseline
