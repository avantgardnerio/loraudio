use codec2::{Codec2, Codec2Mode};
use embassy_futures::select::{select, Either};
use embedded_graphics::mono_font::ascii::FONT_6X10;
use embedded_graphics::mono_font::MonoTextStyleBuilder;
use embedded_graphics::pixelcolor::BinaryColor;
use embedded_graphics::prelude::*;
use embedded_graphics::text::Text;
use esp_idf_svc::hal::adc::continuous::config::Config as AdcContConfig;
use esp_idf_svc::hal::adc::continuous::{AdcDriver as AdcContDriver, AdcMeasurement, Attenuated};
use esp_idf_svc::hal::adc::ADC1;
use esp_idf_svc::hal::gpio::{AnyIOPin, Gpio7};
use esp_idf_svc::hal::gpio::{Input, PinDriver, Pull};
use esp_idf_svc::hal::i2c::config::Config as I2cConfig;
use esp_idf_svc::hal::i2c::{I2cDriver, I2C0};
use esp_idf_svc::hal::units::Hertz;
use ssd1306::mode::BufferedGraphicsMode;
use ssd1306::prelude::*;
use ssd1306::{I2CDisplayInterface, Ssd1306};
use std::future::Future;
use std::thread;
use std::time::{Duration, Instant};

use crate::{TxRequest, RX_CHAN, TX_CHAN};

/// Codec2 MODE_1200: 320 samples → 6 bytes per frame
const CODEC2_FRAME_BYTES: usize = 6;
const CODEC2_FRAME_SAMPLES: usize = 320;

/// Convert 12-bit unsigned ADC sample to signed 16-bit PCM centered at 0.
fn adc_to_pcm(sample: &AdcMeasurement) -> i16 {
    (sample.data() as i16 - 2048) * 16
}

type Display<'a> = Ssd1306<
    I2CInterface<I2cDriver<'a>>,
    DisplaySize128x64,
    BufferedGraphicsMode<DisplaySize128x64>,
>;

pub struct Peripherals {
    pub ptt: AnyIOPin<'static>,
    pub audio_in: Gpio7<'static>, // must stay concrete — ADCPin trait is pin-specific
    pub adc: ADC1<'static>,
    pub i2c: I2C0<'static>,
    pub oled_sda: AnyIOPin<'static>,
    pub oled_scl: AnyIOPin<'static>,
    pub oled_rst: AnyIOPin<'static>,
}

pub async fn init(p: Peripherals, mac_str: heapless::String<18>) -> impl Future<Output = ()> {
    // PRG button on GPIO0 — active LOW with internal pull-up
    let button = PinDriver::input(p.ptt, Pull::Up).unwrap();

    // Continuous ADC for mic on GPIO7 (ADC1_CH6) — DMA at 8kHz
    let adc_config = AdcContConfig::new()
        .sample_freq(Hertz(8000))
        .frame_measurements(320) // 320 samples = 40ms at 8kHz (one Codec2 frame)
        .frames_count(2); // double buffer

    let mut adc = AdcContDriver::new(p.adc, &adc_config, Attenuated::db12(p.audio_in)).unwrap();

    // Reset OLED
    let mut oled_rst = PinDriver::output(p.oled_rst).unwrap();
    oled_rst.set_low().unwrap();
    thread::sleep(Duration::from_millis(50));
    oled_rst.set_high().unwrap();
    thread::sleep(Duration::from_millis(50));

    // I2C for OLED
    let i2c = I2cDriver::new(p.i2c, p.oled_sda, p.oled_scl, &I2cConfig::default()).unwrap();

    // OLED init
    let interface = I2CDisplayInterface::new(i2c);
    let mut display = Ssd1306::new(interface, DisplaySize128x64, DisplayRotation::Rotate0)
        .into_buffered_graphics_mode();
    display.init().unwrap();
    display.set_brightness(Brightness::BRIGHTEST).unwrap();
    log::info!("OLED initialized, MAC: {}", mac_str);

    // Codec2 encoder + decoder (MODE_1200: 320 samples → 6 bytes)
    // Box to avoid bloating the async future's stack frame
    let encoder = Box::new(Codec2::new(Codec2Mode::MODE_1200));
    log::info!("Codec2 encoder initialized");
    let decoder = Box::new(Codec2::new(Codec2Mode::MODE_1200));
    log::info!("Codec2 decoder initialized ({}B/frame)", CODEC2_FRAME_BYTES);

    // Start continuous ADC (DMA)
    adc.start().unwrap();
    log::info!("ADC DMA started at 8kHz");

    async move {
        // Keep oled_rst alive so the pin doesn't float low (holding OLED in reset)
        let _oled_rst = oled_rst;
        app_loop(button, adc, display, &mac_str, encoder, decoder).await;
    }
}

async fn app_loop(
    mut button: PinDriver<'_, Input>,
    mut adc: AdcContDriver<'_>,
    mut display: Display<'_>,
    mac_str: &str,
    mut encoder: Box<Codec2>,
    mut decoder: Box<Codec2>,
) {
    let style = MonoTextStyleBuilder::new()
        .font(&FONT_6X10)
        .text_color(BinaryColor::On)
        .build();

    let mut tx_count: u32 = 0;
    let mut line_buf = heapless::String::<64>::new();
    let mut mic_buf = [AdcMeasurement::new(); 320];
    let mut pcm_buf = [0i16; CODEC2_FRAME_SAMPLES];
    let mut codec_buf = [0u8; CODEC2_FRAME_BYTES];

    // Show initial RX state
    draw_rx_screen(&mut display, mac_str, &style);

    loop {
        match select(RX_CHAN.receive(), button.wait_for_low()).await {
            Either::First(rx_pkt) => {
                if rx_pkt.data.len() == CODEC2_FRAME_BYTES {
                    // Decode Codec2 voice frame
                    let t0 = Instant::now();
                    let mut decode_out = [0i16; CODEC2_FRAME_SAMPLES];
                    decoder.decode(&mut decode_out, &rx_pkt.data);
                    let decode_ms = t0.elapsed().as_millis();

                    // Compute peak amplitude for stats
                    let peak = decode_out.iter().map(|s| s.unsigned_abs()).max().unwrap_or(0);
                    log::info!(
                        "RX Audio [{}B] rssi={}dBm snr={}dB decode={}ms peak={}",
                        rx_pkt.data.len(),
                        rx_pkt.rssi,
                        rx_pkt.snr,
                        decode_ms,
                        peak
                    );

                    display.clear_buffer();
                    Text::new(mac_str, Point::new(1, 10), style)
                        .draw(&mut display)
                        .unwrap();
                    Text::new("RX Audio", Point::new(28, 32), style)
                        .draw(&mut display)
                        .unwrap();

                    line_buf.clear();
                    let _ = core::fmt::write(
                        &mut line_buf,
                        format_args!("RSSI:{} SNR:{}", rx_pkt.rssi, rx_pkt.snr),
                    );
                    Text::new(&line_buf, Point::new(0, 48), style)
                        .draw(&mut display)
                        .unwrap();
                    display.flush().unwrap();
                } else {
                    log::warn!(
                        "RX non-voice [{}B] rssi={}dBm snr={}dB",
                        rx_pkt.data.len(),
                        rx_pkt.rssi,
                        rx_pkt.snr
                    );
                }
            }
            Either::Second(_) => {
                // PTT button pressed — enter TX mode
                log::info!("PTT pressed — switching to TX");

                // Drain any stale mic data
                let _ = adc.read(&mut mic_buf, 0);

                while button.is_low() {
                    // Wait for a fresh mic frame from DMA
                    let count = adc.read_async(&mut mic_buf).await.unwrap_or(0);

                    // Convert ADC samples to PCM
                    for (i, sample) in mic_buf[..count].iter().enumerate() {
                        pcm_buf[i] = adc_to_pcm(sample);
                    }
                    // Zero-pad if short
                    for s in pcm_buf[count..].iter_mut() {
                        *s = 0;
                    }

                    // Encode with Codec2
                    let t0 = Instant::now();
                    encoder.encode(&mut codec_buf, &pcm_buf);
                    let encode_ms = t0.elapsed().as_millis();

                    log::info!(
                        "TX #{} ({}samp) encode={}ms",
                        tx_count,
                        count,
                        encode_ms
                    );

                    // Send encoded frame to radio task
                    let mut data = heapless::Vec::new();
                    let _ = data.extend_from_slice(&codec_buf);
                    TX_CHAN.send(TxRequest { data }).await;

                    // Update display
                    display.clear_buffer();
                    Text::new(mac_str, Point::new(1, 10), style)
                        .draw(&mut display)
                        .unwrap();

                    line_buf.clear();
                    let _ = core::fmt::write(&mut line_buf, format_args!("TX #{}", tx_count));
                    Text::new(&line_buf, Point::new(30, 36), style)
                        .draw(&mut display)
                        .unwrap();
                    display.flush().unwrap();

                    tx_count += 1;
                }

                log::info!("PTT released — back to RX");

                // Redraw RX screen
                draw_rx_screen(&mut display, mac_str, &style);
            }
        }
    }
}

fn draw_rx_screen(
    display: &mut Display<'_>,
    mac_str: &str,
    style: &embedded_graphics::mono_font::MonoTextStyle<BinaryColor>,
) {
    display.clear_buffer();
    Text::new(mac_str, Point::new(1, 10), *style)
        .draw(display)
        .unwrap();
    Text::new("RX Listening", Point::new(16, 36), *style)
        .draw(display)
        .unwrap();
    display.flush().unwrap();
}
