/* Discard defmt sections — they conflict with ESP-IDF flash layout */
SECTIONS {
    /DISCARD/ : {
        *(.defmt .defmt.*)
    }
}
