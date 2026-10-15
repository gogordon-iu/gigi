@echo off
echo ======================================================================
echo   GIGI ROBOTICS: STEP 5 - DUMP EMMC TO GOLDEN IMAGE (.img.zst)
echo ======================================================================
"C:\Python314\python.exe" "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\tools\windows_emmc_image.py" dump --disk 1 --output "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\backups\gigi_golden_20261014.img.zst" --log-file "c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi\scratch\windows_dump.log"
echo.
pause
