fn main() {
    embuild::espidf::sysenv::output();

    // Pass custom linker script to discard defmt sections (from lora-phy dependency)
    println!(
        "cargo:rustc-link-arg=-T{}/defmt-discard.x",
        std::env::var("CARGO_MANIFEST_DIR").unwrap()
    );
}
