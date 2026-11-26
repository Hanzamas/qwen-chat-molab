def _backup_act():
    BACKUP.configure(bk_token.value, bk_repo.value, bk_interval.value)
    if not BACKUP.status["enabled"]:
        return mo.md(f"_Backup mati: {BACKUP.status['last_error'] or 'belum ada token.'}_")
    try:
        if bk_now.value:
            BACKUP.backup_now()
            return mo.callout(mo.md(f"Backup tersimpan di `{BACKUP.repo}`."), kind="success")
        if bk_restore.value:
            BACKUP.restore_latest()
            return mo.callout(mo.md(f"Database dipulihkan dari `{BACKUP.repo}/latest.sqlite`. Muat ulang jendela chat "
                                    f"(pilih chat lagi dari sidebar)."), kind="success")
    except Exception as e:
        return mo.callout(mo.md(f"Gagal: {e}"), kind="danger")
    return mo.md(f"_Backup otomatis aktif ke `{BACKUP.repo}` setiap {BACKUP.interval // 60} menit kalau ada perubahan._")


_backup_act()
