@echo off
echo ======================================================================
echo   GIGI ROBOTICS: STEP 6 - FLASH GOLDEN IMAGE (.img.zst) TO EMMC
echo ======================================================================
"C:\Python314\python.exe" "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\tools\windows_emmc_image.py" flash --disk 1 --input "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\backups\gigi_golden_20261014.img.zst" --yes --log-file "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\scratch\windows_flash.log"
echo.
pause
