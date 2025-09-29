"""
Script para depurar Checklist pasados
"""

import os
import datetime

def delete_checklist_file_after_30_days(directoryPath):

    today = datetime.date.today()
    first = today.replace(day=1)
    lastEntireDate = first - datetime.timedelta(days=1)
    year = lastEntireDate.strftime("%Y")
    lastMonth = lastEntireDate.strftime("%m")
    for day in range(1, 32):
        if day >= 10:
            pathFileToDelete = f"{directoryPath}/CheckList_{year}-{lastMonth}-{day}.xlsx"
        else:
            pathFileToDelete = f"{directoryPath}/CheckList_{year}-{lastMonth}-0{day}.xlsx"

        if os.path.isfile(pathFileToDelete):
            os.remove(pathFileToDelete)
            print(f"File deleted: {pathFileToDelete}")
        else:
            print(f"Don't exist {pathFileToDelete}")

directoryPaths = ["/usr/xal-monitoreo/darrow/excel", "/usr/xal-monitoreo/pal-debitos/excel" ]

for path in directoryPaths:
    delete_checklist_file_after_30_days(path)