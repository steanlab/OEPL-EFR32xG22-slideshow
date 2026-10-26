#include "sl_sleeptimer.h"
#include "images.h"          // IMG_COUNT, images[][5000]
#include "oepl_display.h"    // TODO: сверить имена функций

static sl_sleeptimer_timer_handle_t t;
static uint32_t idx;
static volatile bool due = true;

static void cb(sl_sleeptimer_timer_handle_t *h, void *d) { due = true; }

void slideshow_init(void) {
  idx = 0; due = true;
}

bool slideshow_pending(void) { return due; }   // для sleep manager

void slideshow_process(void) {
  if (!due) return;
  due = false;
  // TODO: инициализировать экран, отдать images[idx] драйверу,
  //       сделать полный refresh, погасить питание экрана
  idx = (idx + 1) % IMG_COUNT;
  sl_sleeptimer_start_timer_ms(&t, 3600UL * 1000UL, cb, NULL, 0, 0);
}
