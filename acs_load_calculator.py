"""
ACS LOCAL PALLET / 40HC LOAD CALCULATOR
=======================================

V2 - CubeMaster comparison build

Purpose:
    Calculate:
    - Cartons per pallet
    - Pallet utilization
    - Cartons per 40HC
    - Container utilization

Current assumptions derived from ACS CubeMaster reports:

PALLET
    Footprint: 1200 x 1000 mm
    Pallet base height: 150 mm
    Maximum total height: 1750 mm
    Usable cargo height: 1600 mm
    All carton orientations tested

40HC
    Internal size: 11998 x 2330 x 2655 mm
    Original carton HEIGHT remains vertical
    LENGTH/WIDTH may rotate on the floor

No external packages required.
"""

from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations


# ============================================================
# CONFIGURATION
# ============================================================

# Euro - Primark pallet
PALLET_LENGTH = 1200
PALLET_WIDTH = 1000
PALLET_BASE_HEIGHT = 150
PALLET_MAX_TOTAL_HEIGHT = 1750

PALLET_USABLE_HEIGHT = (
    PALLET_MAX_TOTAL_HEIGHT - PALLET_BASE_HEIGHT
)


# 40FT High Cube - PAC-D / ACS configuration
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

    floor_utilization: float
    volume_utilization: float

    loaded_height: int

    pattern_description: str


# ============================================================
# CARTON ORIENTATIONS
# ============================================================

def get_all_orientations(length, width, height):
    """
    Generate all unique 3D orientations.

    Example:
        1000 x 400 x 120

    May become:
        1000 x 400 x 120
        400 x 1000 x 120
        1000 x 120 x 400
        120 x 1000 x 400
        400 x 120 x 1000
        120 x 400 x 1000
    """

    unique = set(
        permutations(
            (length, width, height),
            3
        )
    )

    return [
        Orientation(*orientation)
        for orientation in unique
    ]


def get_upright_orientations(length, width, height):
    """
    Keep the supplied carton HEIGHT vertical.

    Only LENGTH and WIDTH can rotate.

    Example:

        1080 x 430 x 60

    becomes either:

        1080 x 430 x 60

    or:

        430 x 1080 x 60

    It cannot become:

        60 x 1080 x 430
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
# SIMPLE GRID PACKING
# ============================================================

def simple_grid_count(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """
    Calculate cartons when all cartons have the same
    floor orientation.
    """

    if (
        carton_length > area_length
        or carton_width > area_width
    ):
        return 0

    along_length = (
        area_length // carton_length
    )

    along_width = (
        area_width // carton_width
    )

    return (
        along_length
        * along_width
    )


# ============================================================
# 2D MIXED BLOCK PACKING
# ============================================================

@lru_cache(maxsize=None)
def best_2d_pack(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """
    Find a good rectangular packing pattern for ONE layer.

    The algorithm tries:

        - Normal grid
        - 90-degree rotated grid
        - Vertical rectangular subdivision
        - Horizontal rectangular subdivision

    This allows patterns such as:

        1 block
        2 blocks
        3 blocks
        4+ blocks

    depending on the carton/container dimensions.

    Returns:

        count
        description
    """

    if (
        area_length <= 0
        or area_width <= 0
    ):
        return 0, "empty"

    best_count = 0
    best_description = "No fit"


    # --------------------------------------------------------
    # FLOOR ORIENTATIONS
    # --------------------------------------------------------

    floor_orientations = {
        (
            carton_length,
            carton_width
        ),
        (
            carton_width,
            carton_length
        )
    }


    # --------------------------------------------------------
    # BASIC GRID
    # --------------------------------------------------------

    for cl, cw in floor_orientations:

        if (
            cl <= area_length
            and cw <= area_width
        ):

            nx = (
                area_length // cl
            )

            ny = (
                area_width // cw
            )

            count = nx * ny

            if count > best_count:

                best_count = count

                best_description = (
                    f"{nx} x {ny} grid "
                    f"({cl}x{cw})"
                )


    # --------------------------------------------------------
    # POSSIBLE BLOCK SPLITS
    # --------------------------------------------------------

    x_splits = set()
    y_splits = set()


    for cl, cw in floor_orientations:

        # Possible splits along length
        n = 1

        while n * cl < area_length:

            x_splits.add(
                n * cl
            )

            n += 1


        # Possible splits along width
        n = 1

        while n * cw < area_width:

            y_splits.add(
                n * cw
            )

            n += 1


    # --------------------------------------------------------
    # VERTICAL BLOCK SPLITS
    # --------------------------------------------------------

    for split in x_splits:

        left_count, left_desc = (
            best_2d_pack(
                split,
                area_width,
                carton_length,
                carton_width
            )
        )

        right_count, right_desc = (
            best_2d_pack(
                area_length - split,
                area_width,
                carton_length,
                carton_width
            )
        )

        total = (
            left_count
            + right_count
        )

        if total > best_count:

            best_count = total

            best_description = (
                "Vertical blocks: "
                f"[{left_desc}] + "
                f"[{right_desc}]"
            )


    # --------------------------------------------------------
    # HORIZONTAL BLOCK SPLITS
    # --------------------------------------------------------

    for split in y_splits:

        bottom_count, bottom_desc = (
            best_2d_pack(
                area_length,
                split,
                carton_length,
                carton_width
            )
        )

        top_count, top_desc = (
            best_2d_pack(
                area_length,
                area_width - split,
                carton_length,
                carton_width
            )
        )

        total = (
            bottom_count
            + top_count
        )

        if total > best_count:

            best_count = total

            best_description = (
                "Horizontal blocks: "
                f"[{bottom_desc}] + "
                f"[{top_desc}]"
            )


    return (
        best_count,
        best_description
    )


# ============================================================
# GENERAL LOAD OPTIMIZER
# ============================================================

def optimize_load(
    carton_l,
    carton_w,
    carton_h,
    load_l,
    load_w,
    load_h,
    allow_vertical_rotation
):
    """
    General load optimizer.

    allow_vertical_rotation=True:
        All six 3D orientations may be tested.

    allow_vertical_rotation=False:
        Original carton HEIGHT remains vertical.
    """

    if allow_vertical_rotation:

        orientations = (
            get_all_orientations(
                carton_l,
                carton_w,
                carton_h
            )
        )

    else:

        orientations = (
            get_upright_orientations(
                carton_l,
                carton_w,
                carton_h
            )
        )


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


    for orientation in orientations:

        # ---------------------------------------------
        # Check vertical fit
        # ---------------------------------------------

        if (
            orientation.height
            > load_h
        ):
            continue


        # ---------------------------------------------
        # Number of vertical layers
        # ---------------------------------------------

        layers = (
            load_h
            // orientation.height
        )

        if layers <= 0:
            continue


        # ---------------------------------------------
        # Solve one floor layer
        # ---------------------------------------------

        per_layer, description = (
            best_2d_pack(
                load_l,
                load_w,
                orientation.length,
                orientation.width
            )
        )


        if per_layer <= 0:
            continue


        # ---------------------------------------------
        # Total cartons
        # ---------------------------------------------

        total = (
            per_layer
            * layers
        )


        # ---------------------------------------------
        # Loaded height
        # ---------------------------------------------

        loaded_height = (
            layers
            * orientation.height
        )


        # ---------------------------------------------
        # Floor utilization
        # ---------------------------------------------

        used_floor_area = (
            per_layer
            * orientation.length
            * orientation.width
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


        # ---------------------------------------------
        # Volume utilization
        # ---------------------------------------------

        used_volume = (
            total
            * original_carton_volume
        )


        volume_utilization = (
            used_volume
            / load_volume
            * 100
        )


        result = LoadResult(

            total_cartons=total,

            cartons_per_layer=per_layer,

            layers=layers,

            carton_length=orientation.length,

            carton_width=orientation.width,

            carton_height=orientation.height,

            floor_utilization=(
                floor_utilization
            ),

            volume_utilization=(
                volume_utilization
            ),

            loaded_height=(
                loaded_height
            ),

            pattern_description=(
                description
            )
        )


        # ---------------------------------------------
        # Keep best result
        # ---------------------------------------------

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
            result.volume_utilization
            > best.volume_utilization
        ):

            best = result


    return best


# ============================================================
# PALLET
# ============================================================

def calculate_pallet(
    length,
    width,
    height
):
    """
    Pallet calculation.

    Currently tests all carton orientations because
    this matches the CubeMaster pallet behaviour seen
    in the supplied ACS examples.
    """

    best_2d_pack.cache_clear()

    return optimize_load(

        length,
        width,
        height,

        PALLET_LENGTH,
        PALLET_WIDTH,
        PALLET_USABLE_HEIGHT,

        allow_vertical_rotation=True
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
    40HC calculation.

    IMPORTANT:

    Supplied carton HEIGHT remains vertical.

    LENGTH and WIDTH may rotate on the container floor.

    This prevents mathematically valid but operationally
    different orientations such as turning a 60 mm-high
    carton onto its 430 mm side.
    """

    best_2d_pack.cache_clear()

    return optimize_load(

        length,
        width,
        height,

        CONTAINER_LENGTH,
        CONTAINER_WIDTH,
        CONTAINER_HEIGHT,

        allow_vertical_rotation=False
    )


# ============================================================
# RESULT PRINTING
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
        "Selected Orientation  : "
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
# INPUT VALIDATION
# ============================================================

def read_dimension(name):

    while True:

        try:

            value = int(
                input(
                    f"Enter carton {name} (mm): "
                )
            )


            if value <= 0:

                print(
                    "Dimension must be greater than 0."
                )

                continue


            return value


        except ValueError:

            print(
                "Please enter a valid whole number."
            )


# ============================================================
# MAIN PROGRAM
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
        "Pallet : all orientations enabled"
    )

    print(
        "40HC   : carton height remains vertical"
    )

    print()


    while True:

        # ----------------------------------------------------
        # INPUT
        # ----------------------------------------------------

        length = read_dimension(
            "LENGTH"
        )

        width = read_dimension(
            "WIDTH"
        )

        height = read_dimension(
            "HEIGHT"
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
        # CONTAINER
        # ----------------------------------------------------

        container_result = (
            calculate_40hc(
                length,
                width,
                height
            )
        )


        # ----------------------------------------------------
        # OUTPUT
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
            "Calculate another carton? (Y/N): "
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