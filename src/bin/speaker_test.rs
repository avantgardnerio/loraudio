//! Speaker test — plays a continuous 440Hz sine wave.
//! Build & flash: cargo build --bin speaker_test && espflash flash -p /dev/ttyACM0 --partition-table target/xtensa-esp32s3-espidf/debug/partition-table.bin target/xtensa-esp32s3-espidf/debug/speaker_test

use esp_idf_svc::hal::delay::BLOCK;
use esp_idf_svc::hal::gpio::{AnyIOPin, PinDriver};
use esp_idf_svc::hal::i2s::config::{
    Config as I2sChannelConfig, DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdGpioConfig,
    StdSlotConfig,
};
use esp_idf_svc::hal::i2s::{I2sDriver, I2sTx};
use esp_idf_svc::hal::peripherals::Peripherals;
use std::thread;
use std::time::Duration;

const SAMPLE_RATE: u32 = 8000;
const FREQ: f32 = 440.0;
const AMPLITUDE: i16 = 8000;
/// 8000/gcd(8000,440) = 200 samples = exactly 11 cycles of 440Hz. Seamless loop.
const BUF_SAMPLES: usize = 200;

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
        p.pins.gpio3, // BCLK
        p.pins.gpio5, // DIN
        None::<AnyIOPin>,
        p.pins.gpio4, // WS
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
    loop {
        i2s.write_all(pcm_as_bytes(&stereo_buf), BLOCK).unwrap();
    }
}
