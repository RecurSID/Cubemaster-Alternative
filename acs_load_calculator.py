"""
ACS LOCAL PALLET / 40HC LOAD CALCULATOR
========================================
V3 - CubeMaster Matching Build

Current inferred ACS rules:

PALLET
------
Footprint          : 1200 x 1000 mm
Pallet base        : 150 mm
Maximum total      : 1750 mm
Usable cargo height: 1600 mm

40HC
----
Internal dimensions:
11998 x 2330 x 2655 mm

ORIENTATION RULE
----------------
For BOTH pallet and 40HC:

- Entered HEIGHT remains vertical/upright.
- LENGTH and WIDTH may swap on the floor.
- Mixed rectangular block patterns are allowed.

Example:
530 x 340 x 180

Allowed:
530 x 340 x 180
340 x 530 x 180

Not allowed:
340 x 180 x 530
180 x 340 x 530
etc.

No external Python packages required.
"""

from dataclasses import dataclass
from functools import lru_cache


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


# ============================================================
# CARTON ORIENTATION
# ============================================================

def get_upright_orientations(
    length,
    width,
    height
):
    """
    Height always remains vertical.

    Only L/W rotation is allowed.

    Example:

    530 x 340 x 180

    becomes:

    530 x 340 x 180

    OR

    340 x 530 x 180
    """

    orientations = {
        (
            length,
            width,
            height
        ),
        (
            width,
            length,
            height
        )
    }

    return [
        Orientation(*orientation)
        for orientation in orientations
    ]


# ============================================================
# VOLUME
# ============================================================

def carton_volume(
    length,
    width,
    height
):

    return (
        length
        * width
        * height
    )


# ============================================================
# 2D BLOCK PACKING ENGINE
# ============================================================

@lru_cache(maxsize=None)
def best_2d_pack(
    area_length,
    area_width,
    carton_length,
    carton_width
):
    """
    Find the best number of cartons that can fit
    on ONE rectangular layer.

    The carton may rotate 90 degrees on the floor.

    The algorithm tests:

    - Normal rectangular grid
    - Rotated rectangular grid
    - Length-wise block splits
    - Width-wise block splits

    This allows mixed patterns similar to:

    1 block
    2 blocks
    3 blocks
    4 blocks

    Returns:

        (
            carton_count,
            pattern_description
        )
    """

    # --------------------------------------------------------
    # INVALID AREA
    # --------------------------------------------------------

    if (
        area_length <= 0
        or area_width <= 0
    ):

        return (
            0,
            "empty"
        )


    best_count = 0

    best_description = (
        "No fit"
    )


    # --------------------------------------------------------
    # ALLOWED FLOOR ORIENTATIONS
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


    # ========================================================
    # BASIC GRID TESTS
    # ========================================================

    for cl, cw in floor_orientations:

        if (
            cl <= area_length
            and
            cw <= area_width
        ):

            along_length = (
                area_length // cl
            )

            along_width = (
                area_width // cw
            )

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


    # ========================================================
    # GENERATE USEFUL SPLIT POSITIONS
    # ========================================================

    x_splits = set()
    y_splits = set()


    for cl, cw in floor_orientations:

        # ----------------------------------------------------
        # LENGTH SPLITS
        # ----------------------------------------------------

        multiplier = 1

        while (
            multiplier * cl
            < area_length
        ):

            x_splits.add(
                multiplier * cl
            )

            multiplier += 1


        # ----------------------------------------------------
        # WIDTH SPLITS
        # ----------------------------------------------------

        multiplier = 1

        while (
            multiplier * cw
            < area_width
        ):

            y_splits.add(
                multiplier * cw
            )

            multiplier += 1


    # ========================================================
    # LENGTH-WISE BLOCK SPLITS
    # ========================================================

    for split in x_splits:

        first_count, first_desc = (
            best_2d_pack(
                split,
                area_width,
                carton_length,
                carton_width
            )
        )


        second_count, second_desc = (
            best_2d_pack(
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


    # ========================================================
    # WIDTH-WISE BLOCK SPLITS
    # ========================================================

    for split in y_splits:

        first_count, first_desc = (
            best_2d_pack(
                area_length,
                split,
                carton_length,
                carton_width
            )
        )


        second_count, second_desc = (
            best_2d_pack(
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


    return (
        best_count,
        best_description
    )


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
    Optimize loading while ALWAYS keeping
    the entered carton height upright.
    """

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


    # ========================================================
    # TEST L/W FLOOR ORIENTATIONS
    # ========================================================

    for orientation in orientations:

        # ----------------------------------------------------
        # CHECK HEIGHT
        # ----------------------------------------------------

        if (
            orientation.height
            > load_h
        ):

            continue


        # ----------------------------------------------------
        # NUMBER OF LAYERS
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

        per_layer, pattern = (
            best_2d_pack(
                load_l,
                load_w,

                orientation.length,
                orientation.width
            )
        )


        if per_layer <= 0:

            continue


        # ----------------------------------------------------
        # TOTAL CARTONS
        # ----------------------------------------------------

        total_cartons = (
            per_layer
            * layers
        )


        # ----------------------------------------------------
        # LOADED HEIGHT
        # ----------------------------------------------------

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
        # CREATE RESULT
        # ----------------------------------------------------

        result = LoadResult(

            total_cartons=(
                total_cartons
            ),

            cartons_per_layer=(
                per_layer
            ),

            layers=(
                layers
            ),

            carton_length=(
                orientation.length
            ),

            carton_width=(
                orientation.width
            ),

            carton_height=(
                orientation.height
            ),

            loaded_height=(
                loaded_height
            ),

            floor_utilization=(
                floor_utilization
            ),

            volume_utilization=(
                volume_utilization
            ),

            pattern_description=(
                pattern
            )
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
# PALLET CALCULATION
# ============================================================

def calculate_pallet(
    length,
    width,
    height
):
    """
    Euro - Primark pallet.

    1200 x 1000 mm

    Maximum cargo height:
    1600 mm above pallet.

    IMPORTANT:
    Entered carton HEIGHT stays upright.
    """

    best_2d_pack.cache_clear()


    return optimize_upright_load(

        length,
        width,
        height,

        PALLET_LENGTH,
        PALLET_WIDTH,
        PALLET_USABLE_HEIGHT
    )


# ============================================================
# 40HC CALCULATION
# ============================================================

def calculate_40hc(
    length,
    width,
    height
):
    """
    ACS / PAC-D 40FT High Cube.

    11998 x 2330 x 2655 mm

    IMPORTANT:
    Entered carton HEIGHT stays upright.
    """

    best_2d_pack.cache_clear()


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

    print(
        "=" * 70
    )

    print(
        title
    )

    print(
        "=" * 70
    )


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
# INPUT VALIDATION
# ============================================================

def read_dimension(
    name
):

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
        "CubeMaster matching mode"
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

    print()


    while True:

        # ====================================================
        # INPUT
        # ====================================================

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


        # ====================================================
        # CALCULATE PALLET
        # ====================================================

        pallet_result = (
            calculate_pallet(
                length,
                width,
                height
            )
        )


        # ====================================================
        # CALCULATE CONTAINER
        # ====================================================

        container_result = (
            calculate_40hc(
                length,
                width,
                height
            )
        )


        # ====================================================
        # DISPLAY
        # ====================================================

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


        # ====================================================
        # ANOTHER CALCULATION?
        # ====================================================

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
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    main()