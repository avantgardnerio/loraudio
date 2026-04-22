use embassy_futures::join::join3;
use embassy_time::Timer;
use embedded_graphics::mono_font::ascii::FONT_6X10;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use esp_idf_svc::hal::gpio::{PinDriver, Pull};
use esp_idf_svc::hal::i2c::I2cDriver;
use esp_idf_svc::hal::i2c::config::Config as I2cConfig;
use esp_idf_svc::hal::peripherals::Peripherals;
use esp_idf_svc::hal::spi::config::Config as SpiConfig;
use esp_idf_svc::hal::spi::{SpiDeviceDriver, SpiDriverConfig};
use esp_idf_svc::hal::task::block_on;
use esp_idf_svc::hal::units::Hertz;
use lora_phy::iv::GenericSx126xInterfaceVariant;
use lora_phy::mod_params::*;
use lora_phy::sx126x::{self, Sx1262, Sx126x, TcxoCtrlVoltage};
use lora_phy::LoRa;
use ssd1306::prelude::*;
use ssd1306::{I2CDisplayInterface, Ssd1306};
use std::thread;
use std::time::Duration;

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    log::info!("Loraudio starting...");

    let peripherals = Peripherals::take().unwrap();

    // LED on GPIO35
    let mut led = PinDriver::output(peripherals.pins.gpio35).unwrap();

    // Enable Vext power (GPIO36 LOW = on) — must keep _vext alive or power turns off
    let mut _vext = PinDriver::output(peripherals.pins.gpio36).unwrap();
    _vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));

    // Reset OLED (GPIO21)
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
    )
    .unwrap();

    // SPI for LoRa: SCK=9, MOSI=10, MISO=11, NSS=8
    let spi = SpiDeviceDriver::new_single(
        peripherals.spi2,
        peripherals.pins.gpio9,
        peripherals.pins.gpio10,
        Some(peripherals.pins.gpio11),
        Some(peripherals.pins.gpio8),
        &SpiDriverConfig::new(),
        &SpiConfig::new().baudrate(Hertz(2_000_000)),
    )
    .unwrap();

    // LoRa control pins — degrade for type erasure (GenericSx126xInterfaceVariant needs uniform types)
    let lora_reset = PinDriver::output(peripherals.pins.gpio12.degrade_output()).unwrap();
    let lora_dio1 = PinDriver::input(peripherals.pins.gpio14.degrade_input(), Pull::Floating).unwrap();
    let lora_busy = PinDriver::input(peripherals.pins.gpio13.degrade_input(), Pull::Floating).unwrap();

    block_on(async {
        // OLED init
        let interface = I2CDisplayInterface::new(i2c);
        let mut display = Ssd1306::new(interface, DisplaySize128x64, DisplayRotation::Rotate0)
            .into_buffered_graphics_mode();
        display.init().unwrap();
        display.set_brightness(Brightness::BRIGHTEST).unwrap();
        log::info!("OLED initialized");

        // LoRa init
        let iv = GenericSx126xInterfaceVariant::new(
            lora_reset, lora_dio1, lora_busy, None, None,
        )
        .unwrap();

        let config = sx126x::Config {
            chip: Sx1262,
            tcxo_ctrl: Some(TcxoCtrlVoltage::Ctrl1V7),
            use_dcdc: true,
            rx_boost: false,
        };

        let mut lora = LoRa::new(Sx126x::new(spi, iv, config), false, embassy_time::Delay)
            .await
            .unwrap();
        log::info!("LoRa radio initialized");

        let mdltn = lora
            .create_modulation_params(
                SpreadingFactor::_7,
                Bandwidth::_125KHz,
                CodingRate::_4_5,
                915_000_000,
            )
            .unwrap();

        let mut tx_params = lora
            .create_tx_packet_params(8, false, true, false, &mdltn)
            .unwrap();

        // Run three concurrent tasks
        join3(
            // Task 1: LED blink (500ms toggle)
            async {
                loop {
                    led.set_high().unwrap();
                    Timer::after_millis(500).await;
                    led.set_low().unwrap();
                    Timer::after_millis(500).await;
                }
            },
            // Task 2: OLED display update
            async {
                let style = MonoTextStyleBuilder::new()
                    .font(&FONT_6X10)
                    .text_color(BinaryColor::On)
                    .build();
                loop {
                    display.clear_buffer();
                    Text::new("LORAUDIO", Point::new(30, 20), style)
                        .draw(&mut display)
                        .unwrap();
                    Text::new("TX Active", Point::new(20, 40), style)
                        .draw(&mut display)
                        .unwrap();
                    display.flush().unwrap();
                    Timer::after_millis(2000).await;
                }
            },
            // Task 3: LoRa TX every 5s — do NOT wrap tx() in select/timeout
            async {
                let mut count: u32 = 0;
                loop {
                    let msg = format!("LORAUDIO #{}", count);
                    log::info!("Sending: {}", msg);

                    lora.prepare_for_tx(&mdltn, &mut tx_params, 22, msg.as_bytes())
                        .await
                        .unwrap();
                    lora.tx().await.unwrap();
                    log::info!("TX complete #{}", count);

                    lora.sleep(false).await.unwrap();
                    count += 1;
                    Timer::after_millis(5000).await;
                }
            },
        )
        .await;
    });
}
