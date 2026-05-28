//! Speaker test — plays a continuous 440Hz sine wave.
//! Pinout: PCB v2 headers shipped J2/J3 FLIPPED, so the amp physically lands on
//! GPIO1/2/3 (not the intended 33/47/48): BCLK=GPIO1, WS/LRCLK=GPIO2, DIN=GPIO3.
//! The OLED shows a live "writes" counter: if it's ticking up, the program is
//! alive and pushing audio into I2S, so silence is a hardware (amp/speaker) fault,
//! not a dead/crashed program.
//! Build & flash: cargo build --bin speaker_test && espflash flash -p <PORT> --partition-table target/xtensa-esp32s3-espidf/debug/partition-table.bin target/xtensa-esp32s3-espidf/debug/speaker_test

use embedded_graphics::mono_font::ascii::FONT_9X18;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use esp_idf_svc::hal::delay::BLOCK;
use esp_idf_svc::hal::gpio::{AnyIOPin, PinDriver};
use esp_idf_svc::hal::i2c::config::Config as I2cConfig;
use esp_idf_svc::hal::i2c::I2cDriver;
use esp_idf_svc::hal::i2s::config::{
    Config as I2sChannelConfig, DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdGpioConfig,
    StdSlotConfig,
};
use esp_idf_svc::hal::i2s::{I2sDriver, I2sTx};
use esp_idf_svc::hal::peripherals::Peripherals;
use ssd1306::mode::BufferedGraphicsMode;
use ssd1306::prelude::*;
use ssd1306::{I2CDisplayInterface, Ssd1306};
use std::thread;
use std::time::Duration;

const SAMPLE_RATE: u32 = 8000;
const FREQ: f32 = 440.0;
const AMPLITUDE: i16 = 8000;
/// 8000/gcd(8000,440) = 200 samples = exactly 11 cycles of 440Hz. Seamless loop.
const BUF_SAMPLES: usize = 200;
/// One write = 200 frames = 25ms of audio, so 40 writes ≈ 1s. Refresh screen then.
const WRITES_PER_REFRESH: u64 = 40;

fn pcm_as_bytes(pcm: &[i16]) -> &[u8] {
    unsafe { core::slice::from_raw_parts(pcm.as_ptr() as *const u8, pcm.len() * 2) }
}

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    log::info!("Speaker test: 440Hz sine wave");

    let p = Peripherals::take().unwrap();

    // Vext power on (GPIO36 LOW)
    let mut vext = PinDriver::output(p.pins.gpio36).unwrap();
    vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));

    // OLED for status readout.
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
    let _oled_rst = oled_rst;

    let draw = |display: &mut _, line1: &str, line2: &str| {
        let d: &mut Ssd1306<_, _, BufferedGraphicsMode<DisplaySize128x64>> = display;
        d.clear_buffer();
        Text::new(line1, Point::new(4, 22), style).draw(d).unwrap();
        Text::new(line2, Point::new(4, 48), style).draw(d).unwrap();
        d.flush().unwrap();
    };

    draw(&mut display, "440Hz tone", "I2S init...");

    // I2S TX for speaker
    let i2s_cfg = StdConfig::new(
        I2sChannelConfig::new()
            .dma_buffer_count(8)
            .frames_per_buffer(320)
            .auto_clear(true),
        StdClkConfig::from_sample_rate_hz(SAMPLE_RATE),
        StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Stereo),
        StdGpioConfig::default(),
    );
    let mut i2s = I2sDriver::<I2sTx>::new_std_tx(
        p.i2s0,
        &i2s_cfg,
        p.pins.gpio1, // BCLK
        p.pins.gpio3, // DIN
        None::<AnyIOPin>,
        p.pins.gpio2, // WS (LRCLK)
    )
    .unwrap();
    i2s.tx_enable().unwrap();
    log::info!("I2S TX enabled");

    // Pre-generate stereo-interleaved sine wave buffer
    let mut stereo_buf = vec![0i16; BUF_SAMPLES * 2];
    for i in 0..BUF_SAMPLES {
        let t = i as f32 / SAMPLE_RATE as f32;
        let sample = (AMPLITUDE as f32 * (2.0 * core::f32::consts::PI * FREQ * t).sin()) as i16;
        stereo_buf[i * 2] = sample;
        stereo_buf[i * 2 + 1] = sample;
    }

    log::info!("Playing 440Hz tone forever...");
    let mut writes: u64 = 0;
    loop {
        i2s.write_all(pcm_as_bytes(&stereo_buf), BLOCK).unwrap();
        writes += 1;
        if writes % WRITES_PER_REFRESH == 0 {
            // If this number is climbing, audio IS being pushed -> fault is the amp/speaker.
            draw(&mut display, "playing", &format!("writes: {}", writes));
        }
    }
}
