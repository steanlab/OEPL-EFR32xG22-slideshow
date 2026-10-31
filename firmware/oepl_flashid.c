// Одноразовая диагностика: читает JEDEC-ID внешней SPI-флэш и печатает его в отладочный UART.
// Только чтение: команды 0xAB (разбудить), 0x9F (ID), 0xB9 (глубокий сон).
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <spidrv.h>
#include "em_gpio.h"
#include "sl_udelay.h"
#include "oepl_efr32_hwtypes.h"

#define FLASHID_REPEATS   5                 // сколько раз повторить вывод (пауза 1 с)
#define FLASHID_RAM_ADDR  0x20007F00UL      // свободная ОЗУ в самом конце: для чтения через gdb

static const char* mfr_name(uint8_t m)
{
  switch (m) {
    case 0xEF: return "Winbond";
    case 0xC2: return "Macronix";
    case 0xC8: return "GigaDevice";
    case 0x85: return "Puya";
    case 0x20: return "XMC or Micron";
    case 0x68: return "Boya";
    case 0x0B: return "XTX";
    case 0x9D: return "ISSI";
    case 0x1F: return "Adesto/Atmel";
    case 0x01: return "Cypress/Spansion";
    case 0xBF: return "SST/Microchip";
    case 0x1C: return "EON";
    case 0xA1: return "Fudan Micro";
    case 0x5E: return "Zbit";
    default:   return "unknown";
  }
}

static bool read_id(const oepl_efr32xg22_flashconfig_t* f, uint8_t id[3])
{
  static SPIDRV_HandleData_t hd;
  SPIDRV_Handle_t h = &hd;
  SPIDRV_Init_t si = SPIDRV_MASTER_DEFAULT;
  si.port = f->usart;
  si.portTx = f->MOSI.port;
  si.pinTx = f->MOSI.pin;
  si.portRx = f->MISO.port;
  si.pinRx = f->MISO.pin;
  si.portClk = f->SCK.port;
  si.pinClk = f->SCK.pin;
  si.bitRate = 1000000;
  si.csControl = spidrvCsControlApplication;

  GPIO_PinModeSet(f->nCS.port, f->nCS.pin, gpioModePushPull, 1);
  SPIDRV_Init(h, &si);

  // Разбудить флэш так же, как это делает oepl_flash_driver.c
  GPIO_PinOutClear(f->nCS.port, f->nCS.pin);
  sl_udelay_wait(20);
  GPIO_PinOutSet(f->nCS.port, f->nCS.pin);
  sl_udelay_wait(35);

  uint8_t wake[] = {0xAB};
  GPIO_PinOutClear(f->nCS.port, f->nCS.pin);
  SPIDRV_MTransmitB(h, wake, sizeof(wake));
  GPIO_PinOutSet(f->nCS.port, f->nCS.pin);
  sl_udelay_wait(100);

  // Прочитать JEDEC ID (до трёх попыток)
  bool ok = false;
  for (int attempt = 0; attempt < 3 && !ok; attempt++) {
    uint8_t buf[4] = {0x9F, 0, 0, 0};
    GPIO_PinOutClear(f->nCS.port, f->nCS.pin);
    SPIDRV_MTransferB(h, buf, buf, 4);
    GPIO_PinOutSet(f->nCS.port, f->nCS.pin);
    id[0] = buf[1];
    id[1] = buf[2];
    id[2] = buf[3];
    ok = (id[0] != 0x00 && id[0] != 0xFF);
    sl_udelay_wait(1000);
  }

  // Отправить флэш в глубокий сон (0xB9), как делает драйвер после чтения
  uint8_t down[] = {0xB9};
  GPIO_PinOutClear(f->nCS.port, f->nCS.pin);
  SPIDRV_MTransmitB(h, down, sizeof(down));
  GPIO_PinOutSet(f->nCS.port, f->nCS.pin);
  sl_udelay_wait(30);

  GPIO_PinModeSet(f->nCS.port, f->nCS.pin, gpioModeInputPull, 1);
  SPIDRV_DeInit(h);
  return ok;
}

void flashid_report(void)
{
  const oepl_efr32xg22_tagconfig_t* cfg = oepl_efr32xg22_get_config();
  if (cfg == NULL || cfg->flash == NULL) {
    printf("\r\n[FLASHID] no flash configuration\r\n");
    fflush(stdout);
    return;
  }

  uint8_t id[3] = {0, 0, 0};
  bool ok = read_id(cfg->flash, id);

  // Результат также кладём в свободную ОЗУ: x/3wx 0x20007F00 в gdb
  volatile uint32_t* ram = (volatile uint32_t*)FLASHID_RAM_ADDR;
  ram[0] = 0xF1A5F1A5UL;                                   // метка «данные есть»
  ram[1] = ((uint32_t)id[0] << 16) | ((uint32_t)id[1] << 8) | id[2];
  ram[2] = ok ? 1u : 0u;

  for (int n = 0; n < FLASHID_REPEATS; n++) {
    printf("\r\n[FLASHID] JEDEC ID: %02X %02X %02X (%s)\r\n",
           id[0], id[1], id[2], ok ? "ok" : "NO ANSWER");
    if (ok) {
      printf("[FLASHID] manufacturer: %s\r\n", mfr_name(id[0]));
      if (id[2] >= 0x10 && id[2] <= 0x1F) {
        unsigned long bytes = 1UL << id[2];
        printf("[FLASHID] capacity code 0x%02X = %lu KB (%lu Mbit)\r\n",
               id[2], bytes / 1024UL, bytes / 131072UL);
      } else {
        printf("[FLASHID] capacity code 0x%02X (non-standard)\r\n", id[2]);
      }
    }
    fflush(stdout);
    for (int i = 0; i < 10; i++) {
      sl_udelay_wait(100000);
    }
  }
}
