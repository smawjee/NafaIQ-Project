$ErrorActionPreference = "Stop"
$log = "D:\NafaIQ-Monorepo\backend\artifacts\signals\corp_actions_crawl.log"
python "D:\NafaIQ-Monorepo\backend\scripts\signals\backfill_corporate_actions_dps.py" *>> $log
exit $LASTEXITCODE
