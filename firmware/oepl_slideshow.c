#include "oepl_slideshow.h"
#include "oepl_display.h"
#include "oepl_hw_abstraction.h"
#include "sl_sleeptimer.h"
#include "images.h"

// Для теста поставь 2 минуты: (2UL * 60UL * 1000UL). Для работы: 1 час.
#define SLIDE_PERIOD_MS (60UL * 60UL * 1000UL)

static sl_sleeptimer_timer_handle_t timer;
static volatile bool due = true;
static size_t idx = 0;

static void on_timer(sl_sleeptimer_timer_handle_t *h, void *d)
{
  (void)h; (void)d;
  due = true;
}

void slideshow_init(void)
{
  oepl_hw_init();
  sl_sleeptimer_start_periodic_timer_ms(&timer, SLIDE_PERIOD_MS, on_timer, NULL, 0, 0);
}

bool slideshow_is_event_pending(void)
{
  return due;
}

void slideshow_process(void)
{
  if (!due) {
    return;
  }
  due = false;
  oepl_display_slideshow_draw(images[idx]);
  idx = (idx + 1) % IMG_COUNT;
}
