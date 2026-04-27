use esp_idf_svc::hal::gpio::AnyIOPin;
use esp_idf_svc::hal::i2s::config::{
    Config as I2sChannelConfig, DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdGpioConfig,
    StdSlotConfig,
};
use esp_idf_svc::hal::i2s::{I2sDriver, I2sTx, I2S0};
use std::future::Future;

use crate::{SPK_REQ, SPK_RESP};

/// Number of stereo samples per Codec2 frame (320 mono × 2 channels)
const STEREO_FRAME_SAMPLES: usize = 320 * 2;

/// Number of frames per packet
const FRAMES_PER_PACKET: usize = 4;

pub struct Peripherals {
    pub i2s: I2S0<'static>,
    pub spk_bclk: AnyIOPin<'static>,
    pub spk_din: AnyIOPin<'static>,
    pub spk_ws: AnyIOPin<'static>,
}

/// Convert i16 PCM slice to &[u8] for I2S write.
fn pcm_as_bytes(pcm: &[i16]) -> &[u8] {
    unsafe { core::slice::from_raw_parts(pcm.as_ptr() as *const u8, pcm.len() * 2) }
}

pub async fn init(p: Peripherals) -> impl Future<Output = ()> {
    let i2s_chan_cfg = I2sChannelConfig::new()
        .dma_buffer_count(4)
        .frames_per_buffer(320)
        .auto_clear(true);
    let std_config = StdConfig::new(
        i2s_chan_cfg,
        StdClkConfig::from_sample_rate_hz(8000),
        StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Stereo),
        StdGpioConfig::default(),
    );
    let mut i2s_tx = I2sDriver::<I2sTx>::new_std_tx(
        p.i2s,
        &std_config,
        p.spk_bclk,
        p.spk_din,
        None::<AnyIOPin>,
        p.spk_ws,
    )
    .unwrap();
    log::info!("I2S TX configured (8kHz stereo 16-bit Philips, 4 DMA bufs)");

    async move {
        i2s_tx.tx_enable().unwrap();
        log::info!("I2S TX enabled");
        speaker_loop(i2s_tx).await;
    }
}

async fn speaker_loop(mut i2s_tx: I2sDriver<'_, I2sTx>) {
    loop {
        // Idle: wait for first audio to kick off playback
        let Some(mut pcm) = SPK_RESP.receive().await else {
            continue; // None while idle — ignore
        };

        // Playing loop
        loop {
            write_packet(&mut i2s_tx, &pcm).await;

            // Get next response (should already be waiting)
            match SPK_RESP.receive().await {
                Some(next_pcm) => pcm = next_pcm,
                None => break, // go idle
            }
        }
    }
}

async fn write_packet(i2s_tx: &mut I2sDriver<'_, I2sTx>, pcm: &[i16]) {
    for frame in 0..FRAMES_PER_PACKET {
        let offset = frame * STEREO_FRAME_SAMPLES;
        let frame_data = &pcm[offset..offset + STEREO_FRAME_SAMPLES];
        i2s_tx.write_async(pcm_as_bytes(frame_data)).await.unwrap();

        if frame == 1 {
            // Request next packet — frames 2+3 still in DMA = ~80ms for app to respond
            SPK_REQ.send(()).await;
        }
    }
}
