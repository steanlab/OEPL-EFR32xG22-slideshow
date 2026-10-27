#include "oepl_slideshow.h"
#include "oepl_display.h"
#include "oepl_hw_abstraction.h"
#include "sl_sleeptimer.h"
#include "sl_udelay.h"
#include "images.h"

extern void oepl_display_slideshow_draw(const uint8_t* bitmap);

#define SLIDE_PERIOD_MS  (2UL * 60UL * 1000UL)   // для работы: (60UL * 60UL * 1000UL)
#define TAP_IGNORE_MS    5000UL                  // защита от повторных срабатываний NFC

// Цвета светодиода (биты: красный 0xE0, зелёный 0x1C, синий 0x03)
#define LED_GREEN  0x1C   // смена по таймеру
#define LED_BLUE   0x03   // смена по касанию NFC

static sl_sleeptimer_timer_handle_t timer;
static volatile bool due = true;
static volatile bool tap = false;
static volatile bool busy = false;
static size_t idx = 0;
static uint32_t last_tap_tick = 0;

static void on_timer(sl_sleeptimer_timer_handle_t *h, void *d)
{
  (void)h; (void)d;
  due = true;
}

static void on_gpio(oepl_hw_gpio_channel_t ch, oepl_hw_gpio_event_t ev)
{
  (void)ev;
  if (ch != NFC_WAKE || busy) {
    return;
  }
  uint32_t now = sl_sleeptimer_get_tick_count();
  if (sl_sleeptimer_tick_to_ms(now - last_tap_tick) < TAP_IGNORE_MS) {
    return;
  }
  last_tap_tick = now;
  tap = true;
}

static void blink(uint8_t color)
{
  oepl_hw_set_led(color, true);
  sl_udelay_wait(150000);   // 150 мс
  oepl_hw_set_led(color, false);
}

void slideshow_init(void)
{
  oepl_hw_init();
  oepl_hw_init_gpio(on_gpio);
  sl_sleeptimer_start_timer_ms(&timer, SLIDE_PERIOD_MS, on_timer, NULL, 0, 0);
}

bool slideshow_is_event_pending(void)
{
  return due || tap;
}

void slideshow_process(void)
{
  if (!due && !tap) {
    return;
  }
  bool by_tap = tap;
  due = false;
  tap = false;
  busy = true;

  blink(by_tap ? LED_BLUE : LED_GREEN);   // моргаем сразу, чтобы был виден отклик
  oepl_display_slideshow_draw(images[idx]);
  idx = (idx + 1) % IMG_COUNT;

  busy = false;
  tap = false;   // касания во время обновления экрана игнорируем
  // Следующая автосмена отсчитывается от конца этого обновления
  sl_sleeptimer_restart_timer_ms(&timer, SLIDE_PERIOD_MS, on_timer, NULL, 0, 0);
}
