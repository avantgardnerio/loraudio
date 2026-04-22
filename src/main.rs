use esp_idf_svc::hal::gpio::PinDriver;
use esp_idf_svc::hal::i2c::I2cDriver;
use esp_idf_svc::hal::i2c::config::Config as I2cConfig;
use esp_idf_svc::hal::peripherals::Peripherals;
use ssd1306::prelude::*;
use ssd1306::I2CDisplayInterface;
use ssd1306::Ssd1306;
use embedded_graphics::mono_font::ascii::FONT_6X10;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use std::thread;
use std::time::Duration;

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    log::info!("Hello from loraudio!");

    let peripherals = Peripherals::take().unwrap();

    // Blink LED
    let mut led = PinDriver::output(peripherals.pins.gpio35).unwrap();

    // Enable Vext power (GPIO36 LOW = on) — powers OLED and external peripherals
    let mut vext = PinDriver::output(peripherals.pins.gpio36).unwrap();
    vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));

    // Reset OLED
    let mut oled_rst = PinDriver::output(peripherals.pins.gpio21).unwrap();
    oled_rst.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));
    oled_rst.set_high().unwrap();
    thread::sleep(Duration::from_millis(50));

    // I2C for OLED: SDA=GPIO17, SCL=GPIO18
    let i2c = I2cDriver::new(
        peripherals.i2c0,
        peripherals.pins.gpio17,
        peripherals.pins.gpio18,
        &I2cConfig::default(),
    ).unwrap();

    let interface = I2CDisplayInterface::new(i2c);
    let mut display = Ssd1306::new(interface, DisplaySize128x64, DisplayRotation::Rotate0)
        .into_buffered_graphics_mode();
    display.init().unwrap();
    display.set_brightness(Brightness::BRIGHTEST).unwrap();

    let text_style = MonoTextStyleBuilder::new()
        .font(&FONT_6X10)
        .text_color(BinaryColor::On)
        .build();

    display.clear_buffer();
    Text::new("LORAUDIO", Point::new(30, 20), text_style)
        .draw(&mut display)
        .unwrap();
    Text::new("Heltec V4 Ready", Point::new(10, 40), text_style)
        .draw(&mut display)
        .unwrap();
    display.flush().unwrap();

    log::info!("OLED initialized");

    // Keep blinking LED
    loop {
        led.set_high().unwrap();
        thread::sleep(Duration::from_millis(500));
        led.set_low().unwrap();
        thread::sleep(Duration::from_millis(500));
    }
}
