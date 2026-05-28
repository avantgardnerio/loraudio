//! I2S pin continuity test — drives one I2S output HIGH at a time, showing
//! which on the OLED. Probe the matching AMP header pad with a multimeter:
//!   screen says "BCLK HIGH" -> AMP BCLK pad should read ~3.3V (good joint),
//!   ~0V means an open between the ESP pin and the AMP pad (cold joint).
//! Build & flash: cargo build --bin io_test && espflash flash -p <PORT> --partition-table target/xtensa-esp32s3-espidf/debug/partition-table.bin target/xtensa-esp32s3-espidf/debug/io_test

use embedded_graphics::mono_font::ascii::FONT_9X18;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use esp_idf_svc::hal::gpio::{PinDriver, Pull};
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
    log::info!("I2S pin continuity test starting");

    let p = Peripherals::take().unwrap();

    // Vext power on (GPIO36 LOW) so the OLED comes up.
    let mut vext = PinDriver::output(p.pins.gpio36).unwrap();
    vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));

    // OLED reset (GPIO21).
    let mut oled_rst = PinDriver::output(p.pins.gpio21).unwrap();
    oled_rst.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));
    oled_rst.set_high().unwrap();
    thread::sleep(Duration::from_millis(50));

    let i2c = I2cDriver::new(p.i2c0, p.pins.gpio17, p.pins.gpio18, &I2cConfig::default()).unwrap();
    let mut display = Ssd1306::new(
        I2CDisplayInterface::new(i2c),
        DisplaySize128x64,
        DisplayRotation::Rotate0,
    )
    .into_buffered_graphics_mode();
    display.init().unwrap();
    display.set_brightness(Brightness::BRIGHTEST).unwrap();

    let style = MonoTextStyleBuilder::new()
        .font(&FONT_9X18)
        .text_color(BinaryColor::On)
        .build();

    // The three I2S lines.
    let mut bclk = PinDriver::output(p.pins.gpio33).unwrap();
    let mut lrc = PinDriver::output(p.pins.gpio47).unwrap();
    let mut din = PinDriver::output(p.pins.gpio48).unwrap();
    bclk.set_low().unwrap();
    lrc.set_low().unwrap();
    din.set_low().unwrap();

    // PTT button (GPIO0, active-low) advances to the next pin.
    let ptt = PinDriver::input(p.pins.gpio0, Pull::Up).unwrap();

    let labels = ["BCLK gpio33", "LRC  gpio47", "DIN  gpio48"];
    let _oled_rst = oled_rst;
    let mut active = 0usize;
    loop {
        // Exactly one line HIGH at a time.
        bclk.set_low().unwrap();
        lrc.set_low().unwrap();
        din.set_low().unwrap();
        match active {
            0 => bclk.set_high().unwrap(),
            1 => lrc.set_high().unwrap(),
            _ => din.set_high().unwrap(),
        }

        let label = labels[active];
        log::info!("Driving HIGH: {}", label);

        display.clear_buffer();
        Text::new(label, Point::new(4, 22), style)
            .draw(&mut display)
            .unwrap();
        Text::new("= 3.3V. PTT>", Point::new(4, 48), style)
            .draw(&mut display)
            .unwrap();
        display.flush().unwrap();

        // Wait for a debounced PTT press-and-release, then advance.
        while ptt.is_high() {
            thread::sleep(Duration::from_millis(10));
        }
        thread::sleep(Duration::from_millis(20)); // debounce
        while ptt.is_low() {
            thread::sleep(Duration::from_millis(10));
        }
        active = (active + 1) % labels.len();
    }
}
