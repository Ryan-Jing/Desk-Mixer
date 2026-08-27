/**************************************************************************************************/
/**
 * @file main.cpp
 * @author  Ryan Jing
 * @brief Firmware entry point. Cooperative superloop with fixed-cadence tasks.
 *        Subsystems are added as they are built -- see README.md for the integration notes.
 *
 * @version 0.1
 * @date 2026-08-26
 *
 * @copyright Copyright (c) 2026
 *
 */
/**************************************************************************************************/

/*------------------------------------------------------------------------------------------------*/
/* HEADERS                                                                                        */
/*------------------------------------------------------------------------------------------------*/

#include <Arduino.h>

/*------------------------------------------------------------------------------------------------*/
/* MACROS                                                                                         */
/*------------------------------------------------------------------------------------------------*/

// Serial diagnostics. Never call Serial from the audio path -- the audio engine
// runs at interrupt priority on a 2.9 ms deadline and logging will cause dropouts.
#define PRINT_DEBUG 1

// Task cadences in milliseconds. Chosen so the worst-case latency of each task is
// obvious by inspection rather than emergent from a scheduler.
#define CONTROL_PERIOD_MS 1
#define LINK_PERIOD_MS 2
#define DISPLAY_PERIOD_MS 30

/*------------------------------------------------------------------------------------------------*/
/* GLOBAL VARIABLES                                                                               */
/*------------------------------------------------------------------------------------------------*/

// Last run time per task. Compared against millis() in loop().
static uint32_t s_last_control_ms = 0;
static uint32_t s_last_link_ms = 0;
static uint32_t s_last_display_ms = 0;

/*------------------------------------------------------------------------------------------------*/
/* FUNCTION PROTOTYPES                                                                            */
/*------------------------------------------------------------------------------------------------*/

/**************************************************************************************************/
/**
 * @name
 * @brief Poll the control surface and apply changes.
 *        Runs at the fastest cadence: this is what makes the device feel responsive.
 *
 *
 */
/**************************************************************************************************/
static void control_task(void);

/**************************************************************************************************/
/**
 * @name
 * @brief Service the host link and any module UARTs.
 *        Kept off the control cadence so a busy host cannot starve the controls.
 *
 *
 */
/**************************************************************************************************/
static void link_task(void);

/**************************************************************************************************/
/**
 * @name
 * @brief Redraw the display.
 *        Slowest cadence -- an SPI panel refresh is expensive and the eye is not.
 *
 *
 */
/**************************************************************************************************/
static void display_task(void);

/*------------------------------------------------------------------------------------------------*/
/* FUNCTION DEFINITIONS                                                                           */
/*------------------------------------------------------------------------------------------------*/

static void control_task(void) {
}

static void link_task(void) {
}

static void display_task(void) {
}

void setup() {
    #ifdef PRINT_DEBUG
        Serial.begin(115200);
    #endif

    // Subsystem initialisation goes here, in dependency order. Bring up anything
    // the audio engine depends on before the engine itself, and let a failed
    // subsystem report and continue rather than blocking startup -- a missing SD
    // card should still leave a usable device.
}

void loop() {
    uint32_t now = millis();

    // Cooperative superloop rather than an RTOS. The Teensy audio library already
    // preempts from an interrupt, so the only job here is to run each task often
    // enough without any of them blocking. Nothing in this loop may busy-wait or
    // call delay(); a task that needs to wait should return and resume next tick.
    if ((now - s_last_control_ms) >= CONTROL_PERIOD_MS) {
        s_last_control_ms = now;
        control_task();
    }

    if ((now - s_last_link_ms) >= LINK_PERIOD_MS) {
        s_last_link_ms = now;
        link_task();
    }

    if ((now - s_last_display_ms) >= DISPLAY_PERIOD_MS) {
        s_last_display_ms = now;
        display_task();
    }
}
