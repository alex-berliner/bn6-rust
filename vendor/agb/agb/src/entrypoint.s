
    .arm
    .section .entrypoint.regular, "ax", %progbits
    .align
.global __start
__start:
    b .Initialise

    @ Filled in by gbafix
    .space 188

.Initialise:
    @ Set interrupt handler
    ldr r0, =InterruptHandler
    ldr r1, =0x03007FFC
    str r0, [r1]

    @ copies ewram section in rom to ewram in ram
    ldr r0, =__ewram_rom_start                 @ load memory address storing start of data for ewram in rom
    ldr r1, =__ewram_data_start                @ load memory address storing location of ewram in ram
    ldr r2, =__ewram_rom_length_halfwords      @ load number of 16 bit values to copy
    swi 0x000B0000                             @ call interrupt CpuSet.
                                               @   r0: source
                                               @   r1: destination
                                               @   r2: length + size information
                                               @
                                               @ see: https://mgba-emu.github.io/gbatek/#swi-0bh-gbands7nds9dsi7dsi9---cpuset

    @ memset the bss section to zeroes
    @ this isn't needed on real hardware or most emulators as BIOS initialises RAM to zeroes before passing to the game
    @ but Quick Boot on the everdrive doesn't initialise RAM. Simple dumb memset, it's only for initialisation so we don't need anything fancy
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
bss_loop:
    cmp r0, r1
    strlt r2, [r0], #4
    blt bss_loop

    ldr r0, =CommonInit
    bx r0

    .arm
    .section .entrypoint.multiboot, "ax", %progbits
    .align
    b __mb_entry
@ Filled in by gbafix
    .space 188
.global __mb_entry
__mb_entry:
    b .Initialise_mb @ multiboot launch point

    .byte 0 @ boot mode, BIOS overwrites this value
    .byte 0 @ slave ID number
    .space 26 @ unused?
    b .Initialise_mb @ Joybus launch point
    .space 4  @ padding for mGBA to not flag it as a libGBA build and boot from cart

.Initialise_mb:
    @ Set interrupt handler
    ldr r0, =InterruptHandler
    ldr r1, =0x03007FFC
    str r0, [r1]

    ldr r0, =CommonInit
    bx r0

    .arm
    .section .entrypoint.common, "ax", %progbits
    .align
.global CommonInit
CommonInit:
    @ copies iwram section in rom to iwram in ram -- at whatever ROM waitstates the BIOS or a flash
    @ cart's firmware left, because the probe that chooses them runs from IWRAM and comes next
    ldr r0, =__iwram_rom_start
    ldr r1, =__iwram_data_start
    ldr r2, =__iwram_rom_length_halfwords
    swi 0x000B0000

    @ set the waitstate control register to the normal value used in manufactured cartridges
    @ (WS0/ROM=3,1 clks, prefetch enabled) -- but only when the cartridge can actually serve reads at
    @ that speed. The Supercard family cannot (its SDRAM misreads at 3/1; SuperFW patches commercial
    @ games' WAITCNT writes for that reason), and a ROM that stores 0x4317 unconditionally boots to a
    @ white screen there: reported on real hardware 2026-09-14 with this ROM. __waitcnt_probe (IWRAM)
    @ checksums the first 16 KiB of ROM at the boot setting and again at 3,1 and keeps the fast
    @ setting only if the two sums agree; otherwise it restores the boot setting.
    ldr r0, =__waitcnt_probe
    mov lr, pc
    bx r0

    @ enable interrupts
    ldr r0, =0x04000208
    ldr r1, =1
    str r1, [r0]

    @ put zero in both r0 and r1
    @ This corresponds to zero for argc and argv (which would technically be required for a c runtime)
    ldr r0, =0
    mov r1, r0

    @ ensure the frame pointer is zero so that stack traces are guaranteed to terminate
    mov r7, r0

    @ load main and branch
    ldr r2, =main
    mov lr, pc
    bx  r2

    @ loop if we end up here
1:
    b 1b
.pool

    .arm
    .section .iwram.waitcnt_probe, "ax", %progbits
    .align
.global __waitcnt_probe
__waitcnt_probe:
    stmfd sp!, {{r4-r6, lr}}
    ldr r4, =0x04000204       @ WAITCNT
    ldrh r6, [r4]             @ the setting we booted with (0 after the BIOS; a flash cart's own otherwise)
    bl .Lwaitcnt_sum
    mov r5, r0                @ the sum read at that setting
    ldr r0, =0x4317           @ WS0/ROM=3,1 clks; SRAM=8 clks; WS2/EEPROM: 8,8 clks; prefetch enabled
    strh r0, [r4]
    bl .Lwaitcnt_sum
    cmp r0, r5                @ the same bytes read at 3,1: equal on a real cartridge and in emulators
    strhne r6, [r4]           @ not equal: this cart cannot serve 3,1 reads; back to the boot setting
    ldmfd sp!, {{r4-r6, lr}}
    bx lr
.Lwaitcnt_sum:                @ r0 = word sum of the first 16 KiB of the cartridge (header, entry, code)
    mov r0, #0
    mov r1, #0x08000000
    add r2, r1, #0x4000
1:
    ldr r3, [r1], #4
    add r0, r0, r3
    cmp r1, r2
    bne 1b
    bx lr
.pool
