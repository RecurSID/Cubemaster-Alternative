"""
ACS LOCAL PALLET / 40HC LOAD CALCULATOR
========================================
V5 - CubeMaster Matching Build

PALLET
------
Footprint           : 1200 x 1000 mm
Pallet base         : 150 mm
Maximum total height: 1750 mm
Usable cargo height : 1600 mm

40HC
----
Internal dimensions : 11998 x 2330 x 2655 mm

ORIENTATION RULE
----------------
For both pallet and 40HC:

- Entered HEIGHT remains vertical/upright.
- LENGTH and WIDTH may rotate 90 degrees on the floor.
- Mixed/interlocking floor patterns are allowed.

PACKING ENGINE
--------------
Stage 1:
    Fast grid + guillotine/block packing.

Stage 2:
    If Stage 1 is below the theoretical area maximum,
    OR-Tools CP-SAT attempts a verified interlocking improvement.

Requires Google OR-Tools (see requirements.txt).
"""

from dataclasses import dataclass
from functools import lru_cache

from hybrid_optimizer import Placement, solve_hybrid_layer


# ============================================================
# CONFIGURATION
# ============================================================

# ---------------- PALLET ----------------

PALLET_LENGTH = 1200
PALLET_WIDTH = 1000

PALLET_BASE_HEIGHT = 150
PALLET_MAX_TOTAL_HEIGHT = 1750

PALLET_USABLE_HEIGHT = (
    PALLET_MAX_TOTAL_HEIGHT
    - PALLET_BASE_HEIGHT
)


# ---------------- 40HC ----------------

CONTAINER_LENGTH = 11998
CONTAINER_WIDTH = 2330
CONTAINER_HEIGHT = 2655


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class Orientation:
    length: int
    width: int
    height: int


@dataclass
class LoadResult:
    total_cartons: int
    cartons_per_layer: int
    layers: int

    carton_length: int
    carton_width: int
    carton_height: int

    loaded_height: int

    floor_utilization: float
    volume_utilization: float

    pattern_description: str
    placements: tuple[Placement, ...] = ()
    solver_status: str = "FAST"


# ============================================================
# ORIENTATION
# ============================================================

def get_upright_orientations(length, width, height):
    """
    Height always stays vertical.

    Only L/W rotation is allowed.
    """

    orientations = {
        (length, width, height),
        (width, length, height)
    }

    return [
        Orientation(*orientation)
        for orientation in orientations
    ]


# ============================================================
# BASIC HELPERS
# ============================================================

def carton_volume(length, width, height):
    return length * width * height


# ============================================================
# STAGE 1:
# FAST GUILLOTINE / BLOCK SOLVER
# ============================================================

@lru_cache(maxsize=None)
def best_2d_pack_guillotine(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """
    Existing fast solver.

    Tests:
    - normal grid
    - rotated grid
    - length-wise rectangular subdivisions
    - width-wise rectangular subdivisions
    """

    if area_length <= 0 or area_width <= 0:
        return 0, "empty"

    # L/W carton rotation makes the loading rectangle symmetric too.  Keeping
    # one canonical area order nearly halves the recursive state space.
    if area_length < area_width:
        return best_2d_pack_guillotine(
            area_width,
            area_length,
            carton_length,
            carton_width
        )

    best_count = 0
    best_description = "No fit"

    floor_orientations = {
        (carton_length, carton_width),
        (carton_width, carton_length)
    }

    area_limit = (
        area_length * area_width
        // (carton_length * carton_width)
    )

    # --------------------------------------------------------
    # BASIC GRIDS
    # --------------------------------------------------------

    for cl, cw in floor_orientations:

        if cl <= area_length and cw <= area_width:

            along_length = area_length // cl
            along_width = area_width // cw

            count = (
                along_length
                * along_width
            )

            if count > best_count:

                best_count = count

                best_description = (
                    f"{along_length} x "
                    f"{along_width} grid "
                    f"({cl}x{cw})"
                )

    if best_count == area_limit:
        return best_count, best_description

    # --------------------------------------------------------
    # POSSIBLE SPLITS
    # --------------------------------------------------------

    x_splits = set()
    y_splits = set()

    for cl, cw in floor_orientations:

        multiplier = 1

        while multiplier * cl < area_length:

            x_splits.add(
                multiplier * cl
            )

            multiplier += 1

        multiplier = 1

        while multiplier * cw < area_width:

            y_splits.add(
                multiplier * cw
            )

            multiplier += 1

    # --------------------------------------------------------
    # LENGTH-WISE SPLITS
    # --------------------------------------------------------

    for split in x_splits:

        if split > area_length // 2:
            continue

        first_count, first_desc = (
            best_2d_pack_guillotine(
                split,
                area_width,
                carton_length,
                carton_width
            )
        )

        second_count, second_desc = (
            best_2d_pack_guillotine(
                area_length - split,
                area_width,
                carton_length,
                carton_width
            )
        )

        total = (
            first_count
            + second_count
        )

        if total > best_count:

            best_count = total

            best_description = (
                "Length blocks: "
                f"[{first_desc}] + "
                f"[{second_desc}]"
            )

            if best_count == area_limit:
                return best_count, best_description

    # --------------------------------------------------------
    # WIDTH-WISE SPLITS
    # --------------------------------------------------------

    for split in y_splits:

        if split > area_width // 2:
            continue

        first_count, first_desc = (
            best_2d_pack_guillotine(
                area_length,
                split,
                carton_length,
                carton_width
            )
        )

        second_count, second_desc = (
            best_2d_pack_guillotine(
                area_length,
                area_width - split,
                carton_length,
                carton_width
            )
        )

        total = (
            first_count
            + second_count
        )

        if total > best_count:

            best_count = total

            best_description = (
                "Width blocks: "
                f"[{first_desc}] + "
                f"[{second_desc}]"
            )

            if best_count == area_limit:
                return best_count, best_description

    return (
        best_count,
        best_description
    )


# ============================================================
# STAGE 2:
# INTERLOCKING PLACEMENT SEARCH
# ============================================================

def rectangles_overlap(a, b):
    """
    Rectangle:
        (x, y, width, height)

    Touching edges are allowed.
    """

    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    return not (
        ax + aw <= bx
        or bx + bw <= ax
        or ay + ah <= by
        or by + bh <= ay
    )


def can_place(
    rect,
    placed,
    area_length,
    area_width
):
    """
    Check:
    - boundary
    - collision
    """

    x, y, w, h = rect

    if x < 0 or y < 0:
        return False

    if x + w > area_length:
        return False

    if y + h > area_width:
        return False

    for other in placed:

        if rectangles_overlap(
            rect,
            other
        ):
            return False

    return True


def generate_candidate_positions(
    placed,
    area_length,
    area_width
):
    """
    Generate useful placement coordinates.

    New rectangles can potentially align with:
    - x = 0
    - y = 0
    - right edges of placed rectangles
    - top edges of placed rectangles

    We combine the candidate X/Y coordinates instead
    of only testing immediate corners.

    This is important for interlocking arrangements.
    """

    xs = {0}
    ys = {0}

    for x, y, w, h in placed:

        xs.add(x)
        xs.add(x + w)

        ys.add(y)
        ys.add(y + h)

    positions = []

    for y in ys:

        if y > area_width:
            continue

        for x in xs:

            if x > area_length:
                continue

            positions.append(
                (x, y)
            )

    # Bottom-left preference
    positions.sort(
        key=lambda p: (
            p[1],
            p[0]
        )
    )

    return positions


def compact_state(placed):
    """
    Canonical state representation for memoization.
    """

    return tuple(
        sorted(placed)
    )


def exact_layer_search(
    area_length,
    area_width,
    carton_length,
    carton_width,
    target
):
    """
    Attempt to place TARGET identical cartons.

    L/W rotation is allowed.

    Returns True when a valid arrangement is found.
    """

    carton_area = (
        carton_length
        * carton_width
    )

    available_area = (
        area_length
        * area_width
    )

    # --------------------------------------------------------
    # AREA BOUND
    # --------------------------------------------------------

    if (
        target * carton_area
        > available_area
    ):
        return False

    orientations = list({
        (
            carton_length,
            carton_width
        ),
        (
            carton_width,
            carton_length
        )
    })

    failed_states = set()

    # Prevent pathological searches from exploding.
    # This is intentionally generous for pallet-sized cases.
    node_counter = [0]
    MAX_NODES = 250000

    def search(placed):

        node_counter[0] += 1

        if node_counter[0] > MAX_NODES:
            return False

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if len(placed) >= target:
            return True

        # ----------------------------------------------------
        # MEMOIZATION
        # ----------------------------------------------------

        state = compact_state(
            placed
        )

        if state in failed_states:
            return False

        # ----------------------------------------------------
        # GENERATE POSITIONS
        # ----------------------------------------------------

        positions = (
            generate_candidate_positions(
                placed,
                area_length,
                area_width
            )
        )

        # ----------------------------------------------------
        # TRY PLACEMENTS
        # ----------------------------------------------------

        for x, y in positions:

            for w, h in orientations:

                rect = (
                    x,
                    y,
                    w,
                    h
                )

                if not can_place(
                    rect,
                    placed,
                    area_length,
                    area_width
                ):
                    continue

                placed.append(
                    rect
                )

                if search(placed):
                    return True

                placed.pop()

        failed_states.add(
            state
        )

        return False

    return search([])


# ============================================================
# HYBRID 2D SOLVER
# ============================================================

@lru_cache(maxsize=None)
def _best_2d_pack_v4_unused(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """
    Hybrid CubeMaster-matching layer solver.

    1. Run the proven fast block solver.
    2. Calculate theoretical area upper bound.
    3. If improvement is mathematically possible,
       try an interlocking placement search.
    """

    # --------------------------------------------------------
    # FAST BASELINE
    # --------------------------------------------------------

    base_count, base_description = (
        best_2d_pack_guillotine(
            area_length,
            area_width,
            carton_length,
            carton_width
        )
    )

    carton_area = (
        carton_length
        * carton_width
    )

    available_area = (
        area_length
        * area_width
    )

    if carton_area <= 0:
        return (
            base_count,
            base_description
        )

    # --------------------------------------------------------
    # THEORETICAL MAXIMUM
    # --------------------------------------------------------

    area_upper_bound = (
        available_area
        // carton_area
    )

    if base_count >= area_upper_bound:

        return (
            base_count,
            base_description
        )

    # --------------------------------------------------------
    # PERFORMANCE GUARD
    # --------------------------------------------------------
    #
    # Exact/interlocking search is mainly useful for pallet-
    # sized layouts.
    #
    # Running a generic backtracking search directly against
    # the entire 40HC floor could be unnecessarily expensive.
    #
    # The existing block solver has already matched our known
    # CubeMaster 40HC regression cases.
    #

    if (
        area_length > 2500
        or area_width > 2500
    ):

        return (
            base_count,
            base_description
        )

    # --------------------------------------------------------
    # TRY TO IMPROVE
    # --------------------------------------------------------

    best_count = base_count

    # Usually we only need +1 or a small improvement.
    # Keep the search bounded.
    search_limit = min(
        area_upper_bound,
        base_count + 3
    )

    for target in range(
        base_count + 1,
        search_limit + 1
    ):

        possible = (
            exact_layer_search(
                area_length,
                area_width,
                carton_length,
                carton_width,
                target
            )
        )

        if possible:

            best_count = target

        else:
            # If target N cannot fit, a larger target
            # cannot fit either.
            break

    if best_count > base_count:

        return (
            best_count,
            (
                "Interlocking pattern "
                f"({best_count} cartons)"
            )
        )

    return (
        base_count,
        base_description
    )


@lru_cache(maxsize=None)
def best_2d_pack_detailed(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """Run the V4 fast solver, then CP-SAT only while a gap remains."""

    base_count, base_pattern = best_2d_pack_guillotine(
        area_length,
        area_width,
        carton_length,
        carton_width
    )
    return solve_hybrid_layer(
        area_length,
        area_width,
        carton_length,
        carton_width,
        base_count,
        base_pattern
    )


@lru_cache(maxsize=None)
def best_2d_pack(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """Compatibility wrapper preserving V4's ``(count, description)`` API."""

    result = best_2d_pack_detailed(
        area_length,
        area_width,
        carton_length,
        carton_width
    )
    return result.count, result.pattern


# ============================================================
# GENERAL LOAD CALCULATION
# ============================================================

def optimize_upright_load(
    carton_l,
    carton_w,
    carton_h,
    load_l,
    load_w,
    load_h
):
    """
    Optimize load while keeping entered HEIGHT vertical.
    """

    # The 2D engine already considers both legal L/W rotations.  Solving the
    # swapped input again is redundant and doubles CP-SAT work.
    orientations = [Orientation(carton_l, carton_w, carton_h)]

    original_carton_volume = (
        carton_volume(
            carton_l,
            carton_w,
            carton_h
        )
    )

    load_volume = (
        load_l
        * load_w
        * load_h
    )

    best = None

    # ========================================================
    # TEST FLOOR ORIENTATIONS
    # ========================================================

    for orientation in orientations:

        if orientation.height > load_h:
            continue

        # ----------------------------------------------------
        # LAYERS
        # ----------------------------------------------------

        layers = (
            load_h
            // orientation.height
        )

        if layers <= 0:
            continue

        # ----------------------------------------------------
        # SOLVE ONE LAYER
        # ----------------------------------------------------

        layer_solution = (
            best_2d_pack_detailed(
                load_l,
                load_w,
                orientation.length,
                orientation.width
            )
        )

        per_layer = layer_solution.count
        pattern = layer_solution.pattern

        if per_layer <= 0:
            continue

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        total_cartons = (
            per_layer
            * layers
        )

        loaded_height = (
            layers
            * orientation.height
        )

        # ----------------------------------------------------
        # FLOOR UTILIZATION
        # ----------------------------------------------------

        carton_floor_area = (
            orientation.length
            * orientation.width
        )

        used_floor_area = (
            per_layer
            * carton_floor_area
        )

        available_floor_area = (
            load_l
            * load_w
        )

        floor_utilization = (
            used_floor_area
            / available_floor_area
            * 100
        )

        # ----------------------------------------------------
        # VOLUME UTILIZATION
        # ----------------------------------------------------

        used_volume = (
            total_cartons
            * original_carton_volume
        )

        volume_utilization = (
            used_volume
            / load_volume
            * 100
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        result = LoadResult(
            total_cartons=total_cartons,
            cartons_per_layer=per_layer,
            layers=layers,

            carton_length=orientation.length,
            carton_width=orientation.width,
            carton_height=orientation.height,

            loaded_height=loaded_height,

            floor_utilization=floor_utilization,
            volume_utilization=volume_utilization,

            pattern_description=pattern,
            placements=layer_solution.placements,
            solver_status=layer_solution.status
        )

        # ----------------------------------------------------
        # SELECT BEST
        # ----------------------------------------------------

        if best is None:

            best = result

        elif (
            result.total_cartons
            > best.total_cartons
        ):

            best = result

        elif (
            result.total_cartons
            == best.total_cartons
            and
            result.floor_utilization
            > best.floor_utilization
        ):

            best = result

    return best


# ============================================================
# CACHE RESET
# ============================================================

def clear_packing_caches():

    best_2d_pack.cache_clear()
    best_2d_pack_detailed.cache_clear()
    best_2d_pack_guillotine.cache_clear()


# ============================================================
# PALLET
# ============================================================

def calculate_pallet(
    length,
    width,
    height
):
    """
    Euro - Primark pallet:
        1200 x 1000 mm

    Usable cargo height:
        1600 mm

    Entered carton height stays upright.
    """

    clear_packing_caches()

    return optimize_upright_load(
        length,
        width,
        height,

        PALLET_LENGTH,
        PALLET_WIDTH,
        PALLET_USABLE_HEIGHT
    )


# ============================================================
# 40HC
# ============================================================

def calculate_40hc(
    length,
    width,
    height
):
    """
    ACS / PAC-D 40FT High Cube:
        11998 x 2330 x 2655 mm

    Entered carton height stays upright.
    """

    clear_packing_caches()

    return optimize_upright_load(
        length,
        width,
        height,

        CONTAINER_LENGTH,
        CONTAINER_WIDTH,
        CONTAINER_HEIGHT
    )


# ============================================================
# RESULT OUTPUT
# ============================================================

def print_result(
    title,
    result
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    if result is None:

        print(
            "Carton cannot fit."
        )

        return

    print(
        f"Cartons               : "
        f"{result.total_cartons:,}"
    )

    print(
        f"Cartons / Layer       : "
        f"{result.cartons_per_layer:,}"
    )

    print(
        f"Layers                : "
        f"{result.layers:,}"
    )

    print(
        f"Orientation           : "
        f"{result.carton_length} x "
        f"{result.carton_width} x "
        f"{result.carton_height} mm"
    )

    print(
        f"Loaded Height         : "
        f"{result.loaded_height:,} mm"
    )

    print(
        f"Floor Utilization     : "
        f"{result.floor_utilization:.2f}%"
    )

    print(
        f"Volume Utilization    : "
        f"{result.volume_utilization:.2f}%"
    )

    print(
        f"Packing Pattern       : "
        f"{result.pattern_description}"
    )


# ============================================================
# INPUT
# ============================================================

def read_dimension(name):

    while True:

        try:

            value = int(
                input(
                    f"Enter carton "
                    f"{name} (mm): "
                )
            )

            if value <= 0:

                print(
                    "Dimension must be "
                    "greater than 0."
                )

                continue

            return value

        except ValueError:

            print(
                "Please enter a valid "
                "whole number."
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "=" * 70
    )

    print(
        "          ACS LOCAL PALLET / 40HC CALCULATOR"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "CubeMaster matching mode - V5"
    )

    print()

    print(
        "Pallet : entered height stays upright"
    )

    print(
        "40HC   : entered height stays upright"
    )

    print(
        "L/W    : 90-degree floor rotation enabled"
    )

    print(
        "Packing: fast guillotine + CP-SAT interlocking optimization"
    )

    print()

    while True:

        # ----------------------------------------------------
        # INPUT
        # ----------------------------------------------------

        length = (
            read_dimension(
                "LENGTH"
            )
        )

        width = (
            read_dimension(
                "WIDTH"
            )
        )

        height = (
            read_dimension(
                "HEIGHT"
            )
        )

        print()

        print(
            f"Calculating "
            f"{length} x "
            f"{width} x "
            f"{height} mm..."
        )

        # ----------------------------------------------------
        # PALLET
        # ----------------------------------------------------

        pallet_result = (
            calculate_pallet(
                length,
                width,
                height
            )
        )

        # ----------------------------------------------------
        # 40HC
        # ----------------------------------------------------

        container_result = (
            calculate_40hc(
                length,
                width,
                height
            )
        )

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        print_result(
            "PALLET RESULT",
            pallet_result
        )

        print_result(
            "40HC CONTAINER RESULT",
            container_result
        )

        print()

        print(
            "=" * 70
        )

        # ----------------------------------------------------
        # AGAIN?
        # ----------------------------------------------------

        again = input(
            "Calculate another carton? "
            "(Y/N): "
        ).strip().lower()

        if again not in (
            "y",
            "yes"
        ):

            break

        print()

    print()

    print(
        "Calculator closed."
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
