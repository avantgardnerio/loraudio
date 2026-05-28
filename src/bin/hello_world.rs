//! Minimal board bringup test — prints "Hello World" on the OLED.
//! Proves Vext power, I2C, and the SSD1306 display are all wired correctly.
//! Build & flash: cargo build --bin hello_world && espflash flash -p <PORT> --partition-table target/xtensa-esp32s3-espidf/debug/partition-table.bin target/xtensa-esp32s3-espidf/debug/hello_world

use embedded_graphics::mono_font::ascii::FONT_9X18;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use esp_idf_svc::hal::gpio::PinDriver;
use esp_idf_svc::hal::i2c::config::Config as I2cConfig;
use esp_idf_svc::hal::i2c::I2cDriver;
use esp_idf_svc::hal::peripherals::Peripherals;
use ssd1306::prelude::*;
use ssd1306::{I2CDisplayInterface, Ssd1306};
use std::thread;
use std::time::Duration;

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    log::info!("Hello World OLED test starting");

    let p = Peripherals::take().unwrap();

    // Vext power on (GPIO36 LOW) — OLED is dead without this.
    let mut vext = PinDriver::output(p.pins.gpio36).unwrap();
    vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));
    log::info!("Vext enabled");

    // Reset the OLED (GPIO21).
    let mut oled_rst = PinDriver::output(p.pins.gpio21).unwrap();
    oled_rst.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));
    oled_rst.set_high().unwrap();
    thread::sleep(Duration::from_millis(50));

    // I2C for OLED: SDA=GPIO17, SCL=GPIO18.
    let i2c = I2cDriver::new(p.i2c0, p.pins.gpio17, p.pins.gpio18, &I2cConfig::default()).unwrap();

    let interface = I2CDisplayInterface::new(i2c);
    let mut display = Ssd1306::new(interface, DisplaySize128x64, DisplayRotation::Rotate0)
        .into_buffered_graphics_mode();
    display.init().unwrap();
    display.set_brightness(Brightness::BRIGHTEST).unwrap();
    log::info!("OLED initialized");

    let style = MonoTextStyleBuilder::new()
        .font(&FONT_9X18)
        .text_color(BinaryColor::On)
        .build();

    display.clear_buffer();
    Text::new("Hello", Point::new(8, 24), style)
        .draw(&mut display)
        .unwrap();
    Text::new("World!", Point::new(8, 48), style)
        .draw(&mut display)
        .unwrap();
    display.flush().unwrap();
    log::info!("Drawn to screen — if you can read this, the board works.");

    // Keep oled_rst alive so the pin doesn't float low and hold the OLED in reset.
    let _oled_rst = oled_rst;
    loop {
        thread::sleep(Duration::from_secs(1));
    }
}
