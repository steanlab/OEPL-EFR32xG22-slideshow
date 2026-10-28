#include "oepl_slideshow.h"
#include "oepl_display.h"
#include "oepl_hw_abstraction.h"
#include "sl_sleeptimer.h"
#include "sl_udelay.h"
#include "images.h"

extern void oepl_display_slideshow_draw(const uint8_t* bitmap);
extern volatile uint8_t slideshow_draw_attempts;

#define SLIDE_PERIOD_MS  (60UL * 60UL * 1000UL)   // период смены
#define TITLE_HOLD_MS    (30UL * 1000UL)          // сколько держится заглавный слайд
#define TAP_IGNORE_MS    5000UL                   // защита от повторных срабатываний NFC
#define MIN_GAP_MS       0UL                      // 0 = без ограничения между касаниями
#define DEBUG_SEQUENTIAL 1                        // ВРЕМЕННО: 1 = по порядку, пауза 5 с; 0 = обычный режим

// Цвета светодиода на этой плате
#define LED_RED    0x03   // смена по касанию NFC
#define LED_BLUE   0x1C   // смена по таймеру
#define LED_GREEN  0xE0   // касание слишком рано (при MIN_GAP_MS > 0)

static sl_sleeptimer_timer_handle_t timer;
static volatile bool due = true;
static volatile bool tap = false;
static volatile bool rejected = false;
static volatile bool busy = false;
static uint32_t last_tap_tick = 0;
static uint32_t last_draw_end_tick = 0;
static bool have_drawn = false;

// ---------------- Порядок показа: заглавный слайд, затем случайно -----------
static bool first_slide = true;
static uint8_t order[IMG_COUNT > 1 ? IMG_COUNT : 1];
static size_t order_len = 0;
static size_t order_pos = 0;
static size_t last_shown = 0;
static uint32_t rng_state = 0x12345678;

static uint32_t rng_next(void)
{
  uint32_t x = rng_state;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  rng_state = x;
  return x;
}

static void reshuffle(void)
{
  rng_state ^= sl_sleeptimer_get_tick_count() * 2654435761UL;
  if (rng_state == 0) {
    rng_state = 0x12345678;
  }
  order_len = IMG_COUNT - 1;
  for (size_t i = 0; i < order_len; i++) {
    order[i] = (uint8_t)(i + 1);
  }
  for (size_t i = order_len - 1; i > 0; i--) {
    size_t j = rng_next() % (i + 1);
    uint8_t t = order[i];
    order[i] = order[j];
    order[j] = t;
  }
  if (order_len > 1 && order[0] == last_shown) {
    uint8_t t = order[0];
    order[0] = order[order_len - 1];
    order[order_len - 1] = t;
  }
  order_pos = 0;
}

static size_t next_index(void)
{
#if DEBUG_SEQUENTIAL
  static size_t seq = 0;
  size_t i = seq;
  seq = (seq + 1) % IMG_COUNT;
  return i;                         // 0, 1, 2, ... по алфавиту, потом снова 0
#else
  if (first_slide) {
    first_slide = false;
    last_shown = 0;
    return 0;                       // заглавный слайд
  }
  if (IMG_COUNT <= 1) {
    return 0;
  }
  if (order_pos >= order_len) {
    reshuffle();
  }
  last_shown = order[order_pos++];
  return last_shown;
#endif
}

// ---------------- Таймер, NFC, светодиод ------------------------------------
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
  if (have_drawn && sl_sleeptimer_tick_to_ms(now - last_draw_end_tick) < MIN_GAP_MS) {
    rejected = true;
    return;
  }
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
  return due || tap || rejected;
}

void slideshow_process(void)
{
  if (rejected) {
    rejected = false;
    blink(LED_GREEN);
  }
  if (!due && !tap) {
    return;
  }
  bool by_tap = tap;
  due = false;
  tap = false;
  busy = true;

  size_t shown = next_index();
  blink(by_tap ? LED_RED : LED_BLUE);
  oepl_display_slideshow_draw(images[shown]);

  // ВРЕМЕННО, диагностика очереди рисования (после обновления экрана):
  // 2-3 красные вспышки = очередь была пустой, повтор помог; 5 = не удалось
  if (slideshow_draw_attempts != 1) {
    int flashes = (slideshow_draw_attempts == 0) ? 5 : slideshow_draw_attempts;
    for (int n = 0; n < flashes; n++) {
      blink(LED_RED);
      sl_udelay_wait(250000);
    }
  }

  last_draw_end_tick = sl_sleeptimer_get_tick_count();
  have_drawn = true;
  busy = false;
  tap = false;
  rejected = false;

  uint32_t wait_ms = (shown == 0 && IMG_COUNT > 1) ? TITLE_HOLD_MS : SLIDE_PERIOD_MS;
#if DEBUG_SEQUENTIAL
  wait_ms = 5UL * 1000UL;           // следующая смена через 5 с после обновления
#endif
  sl_sleeptimer_restart_timer_ms(&timer, wait_ms, on_timer, NULL, 0, 0);
}
