//! Audio loopback test — hold PTT to record, release to play back.
//! Build & flash: cargo build --bin audio_test && espflash flash -p /dev/ttyACM1 target/xtensa-esp32s3-espidf/debug/audio_test

use esp_idf_svc::hal::adc::continuous::config::Config as AdcContConfig;
use esp_idf_svc::hal::adc::continuous::{AdcDriver as AdcContDriver, AdcMeasurement, Attenuated};
use esp_idf_svc::hal::delay::BLOCK;
use esp_idf_svc::hal::gpio::{AnyIOPin, PinDriver, Pull};
use esp_idf_svc::hal::i2s::config::{
    Config as I2sChannelConfig, DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdGpioConfig,
    StdSlotConfig,
};
use esp_idf_svc::hal::i2s::{I2sDriver, I2sTx};
use esp_idf_svc::hal::peripherals::Peripherals;
use esp_idf_svc::hal::units::Hertz;
use std::thread;
use std::time::Duration;

/// Max recording: 5 seconds at 8kHz = 40000 mono samples
const MAX_SAMPLES: usize = 8000 * 5;

/// Convert 12-bit unsigned ADC to signed 16-bit PCM.
fn adc_to_pcm(sample: &AdcMeasurement) -> i16 {
    (sample.data() as i16 - 2048) * 16
}

fn pcm_as_bytes(pcm: &[i16]) -> &[u8] {
    unsafe { core::slice::from_raw_parts(pcm.as_ptr() as *const u8, pcm.len() * 2) }
}

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    log::info!("Audio loopback test starting...");

    let p = Peripherals::take().unwrap();

    // Vext power on (GPIO36 LOW)
    let mut vext = PinDriver::output(p.pins.gpio36).unwrap();
    vext.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));

    // PTT button (GPIO0, active LOW)
    let button = PinDriver::input(p.pins.gpio0, Pull::Up).unwrap();

    // ADC continuous for mic on GPIO7 at 8kHz
    let adc_cfg = AdcContConfig::new()
        .sample_freq(Hertz(8000))
        .frame_measurements(320)
        .frames_count(2);
    let mut adc = AdcContDriver::new(p.adc1, &adc_cfg, Attenuated::db12(p.pins.gpio7)).unwrap();

    // I2S TX for speaker
    let i2s_cfg = StdConfig::new(
        I2sChannelConfig::new()
            .dma_buffer_count(8)
            .frames_per_buffer(320)
            .auto_clear(true),
        StdClkConfig::from_sample_rate_hz(8000),
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

    // Heap buffers
    let mut mic_buf = vec![AdcMeasurement::new(); 320];
    let mut rec_buf = vec![0i16; MAX_SAMPLES]; // mono recording buffer
    let mut stereo_buf = vec![0i16; 640]; // one frame stereo interleaved

    log::info!("Ready — hold PTT to record (max 5s), release to play back");

    adc.start().unwrap();

    loop {
        // Wait for PTT press
        while button.is_high() {
            thread::sleep(Duration::from_millis(10));
        }

        // --- Record ---
        log::info!("Recording...");
        let _ = adc.read(&mut mic_buf, 0); // drain stale
        let mut rec_len: usize = 0;

        while button.is_low() && rec_len < MAX_SAMPLES {
            let count = adc.read(&mut mic_buf, 100).unwrap_or(0);
            let remaining = MAX_SAMPLES - rec_len;
            let n = count.min(remaining);
            for i in 0..n {
                rec_buf[rec_len + i] = adc_to_pcm(&mic_buf[i]);
            }
            rec_len += n;
        }
        log::info!("Recorded {} samples ({}ms)", rec_len, rec_len / 8);

        // --- Play back ---
        log::info!("Playing...");
        let mut offset = 0;
        while offset < rec_len {
            let chunk = (rec_len - offset).min(320);
            for i in 0..chunk {
                stereo_buf[i * 2] = rec_buf[offset + i];
                stereo_buf[i * 2 + 1] = rec_buf[offset + i];
            }
            // Zero-pad last chunk if short
            for i in chunk..320 {
                stereo_buf[i * 2] = 0;
                stereo_buf[i * 2 + 1] = 0;
            }
            i2s.write_all(pcm_as_bytes(&stereo_buf[..chunk * 2]), BLOCK)
                .unwrap();
            offset += chunk;
        }
        log::info!("Playback done");
    }
}
