@echo off
rem Arranca el cazador: sirve el kernel por TFTP, espera a U-Boot, lo carga y
rem lo arranca. Todo va a RAM: no toca la NAND.
cd /d "%~dp0"

echo ============================================================
echo  Arranque del kernel 5.6.3 en el Genexis Pure ED500
echo ============================================================
echo.
echo  1. Este programa espera hasta 3 horas a que la placa arranque.
echo  2. Sirve uImage-563 por TFTP (puerto 69 o, si esta ocupado, 6969).
echo  3. Cuando enciendas la placa, caza U-Boot y arranca el kernel.
echo  4. Todo queda en: logs\try563_v2.log
echo.
echo  Cable: COM4 a 115200. Red: LAN (PC en 192.168.1.160)
echo  Ojo: si otra ventana tiene COM4 abierto, cierrala antes.
echo.
pause

where python >nul 2>&1
if %errorlevel%==0 (
    python catch_final.py
    goto fin
)
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 catch_final.py
    goto fin
)
echo.
echo [!] No encuentro Python en el PATH. Instalalo o ejecuta a mano:
echo     python catch_final.py
:fin
echo.
pause
