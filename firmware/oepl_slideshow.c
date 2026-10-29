#include "oepl_slideshow.h"
#include "oepl_display.h"
#include "oepl_hw_abstraction.h"
#include "oepl_efr32_hwtypes.h"
#include "em_gpio.h"
#include "sl_sleeptimer.h"
#include "sl_udelay.h"
#include "images.h"

extern void oepl_display_slideshow_draw(const uint8_t* bitmap);

// ---------------- Настройки ----------------
#define SLIDE_PERIOD_MS    (60UL * 60UL * 1000UL)   // период автосмены
#define TITLE_HOLD_MS      (30UL * 1000UL)          // заглавный слайд после включения
#define TAP_IGNORE_MS      5000UL                   // защита от повторных срабатываний NFC
#define LONG_PRESS_MS      1500UL                   // порог долгого нажатия
#define BTN_PRESSED_LEVEL  0                        // уровень на пине при нажатой кнопке
// Долгое нажатие: 1 = предыдущая картинка, 2 = заглавный слайд, 3 = пауза/продолжение автосмены
#define LONG_PRESS_ACTION  3

// Цвета светодиода на этой плате
#define LED_RED    0x03   // ручная смена (NFC или короткое нажатие)
#define LED_BLUE   0x1C   // смена по таймеру
#define LED_GREEN  0xE0   // долгое нажатие

typedef enum { REQ_NONE, REQ_NEXT, REQ_PREV, REQ_TITLE } request_t;

static sl_sleeptimer_timer_handle_t timer;
static sl_sleeptimer_timer_handle_t long_timer;
static volatile bool due = true;
static volatile bool tap = false;
static volatile bool btn_short = false;
static volatile bool btn_long = false;
static volatile bool btn_down = false;
static volatile bool btn_long_fired = false;
static volatile bool busy = false;
static bool paused = false;
static bool boot_done = false;
static uint32_t last_tap_tick = 0;
static size_t cur_shown = 0;
static size_t prev_shown = 0;

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
  if (first_slide) {
    first_slide = false;
    return 0;                       // заглавный слайд
  }
  if (IMG_COUNT <= 1) {
    return 0;
  }
  if (order_pos >= order_len) {
    reshuffle();
  }
  return order[order_pos++];
}

// ---------------- Таймер, NFC, кнопка, светодиод ----------------------------
static void on_timer(sl_sleeptimer_timer_handle_t *h, void *d)
{
  (void)h; (void)d;
  due = true;
}

static void on_long_timer(sl_sleeptimer_timer_handle_t *h, void *d)
{
  (void)h; (void)d;
  if (btn_down) {
    btn_long_fired = true;          // после этого отпускание не считается коротким нажатием
    if (!busy) {
      btn_long = true;
    }
  }
}

static bool button_is_down(oepl_hw_gpio_channel_t ch)
{
  const oepl_efr32xg22_tagconfig_t* cfg = oepl_efr32xg22_get_config();
  if (cfg == NULL || cfg->gpio == NULL) {
    return false;
  }
  const oepl_efr32xg22_gpio_t* b = (ch == BUTTON_1) ? &cfg->gpio->button1 : &cfg->gpio->button2;
  if (b->port == gpioPortInvalid) {
    return false;
  }
  return GPIO_PinInGet(b->port, b->pin) == BTN_PRESSED_LEVEL;
}

static void on_gpio(oepl_hw_gpio_channel_t ch, oepl_hw_gpio_event_t ev)
{
  (void)ev;   // событие не различает фронты, поэтому читаем уровень на пине сами

  if (ch == NFC_WAKE) {
    if (busy) {
      return;
    }
    uint32_t now = sl_sleeptimer_get_tick_count();
    if (sl_sleeptimer_tick_to_ms(now - last_tap_tick) < TAP_IGNORE_MS) {
      return;
    }
    last_tap_tick = now;
    tap = true;
  } else if (ch == BUTTON_1 || ch == BUTTON_2) {
    bool down = button_is_down(ch);
    if (down && !btn_down) {
      btn_down = true;
      btn_long_fired = false;
      sl_sleeptimer_restart_timer_ms(&long_timer, LONG_PRESS_MS, on_long_timer, NULL, 0, 0);
    } else if (!down && btn_down) {
      btn_down = false;
      sl_sleeptimer_stop_timer(&long_timer);
      if (!btn_long_fired && !busy) {
        btn_short = true;
      }
    }
  }
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
  return due || tap || btn_short || btn_long;
}

void slideshow_process(void)
{
  request_t req = REQ_NONE;
  uint8_t led = LED_BLUE;

  if (btn_long) {
    btn_long = false;
#if LONG_PRESS_ACTION == 1
    req = REQ_PREV;
    led = LED_GREEN;
#elif LONG_PRESS_ACTION == 2
    req = REQ_TITLE;
    led = LED_GREEN;
#else
    paused = !paused;
    if (paused) {
      sl_sleeptimer_stop_timer(&timer);
      due = false;
      for (int n = 0; n < 3; n++) {      // 3 вспышки = пауза
        blink(LED_GREEN);
        sl_udelay_wait(200000);
      }
    } else {
      sl_sleeptimer_restart_timer_ms(&timer, SLIDE_PERIOD_MS, on_timer, NULL, 0, 0);
      blink(LED_GREEN);                  // 1 вспышка = продолжение
    }
#endif
  }

  if (req == REQ_NONE) {
    if (tap || btn_short) {
      req = REQ_NEXT;
      led = LED_RED;
    } else if (due) {
      req = REQ_NEXT;
      led = LED_BLUE;
    }
  }
  if (req == REQ_NONE) {
    return;
  }

  due = false;
  tap = false;
  btn_short = false;
  busy = true;

  size_t shown;
  if (req == REQ_TITLE) {
    shown = 0;
  } else if (req == REQ_PREV) {
    shown = prev_shown;
  } else {
    shown = next_index();
  }

  bool is_boot = !boot_done;
  boot_done = true;

  blink(led);
  oepl_display_slideshow_draw(images[shown]);

  prev_shown = cur_shown;
  cur_shown = shown;
  last_shown = shown;

  busy = false;
  tap = false;            // нажатия и касания во время обновления экрана игнорируем
  btn_short = false;

  if (!paused) {
    // Заглавный слайд после включения держим недолго, остальные по обычному периоду
    uint32_t wait_ms = (is_boot && IMG_COUNT > 1) ? TITLE_HOLD_MS : SLIDE_PERIOD_MS;
    sl_sleeptimer_restart_timer_ms(&timer, wait_ms, on_timer, NULL, 0, 0);
  }
}
