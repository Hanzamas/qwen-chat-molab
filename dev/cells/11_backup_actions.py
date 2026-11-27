def _backup_act():
    BACKUP.configure(bk_token.value or ctl_hf.value, bk_repo.value, bk_interval.value)
    if not BACKUP.status["enabled"]:
        return mo.md(f"_Backup is off: {BACKUP.status['last_error'] or 'no token yet.'}_")
    try:
        if bk_now.value:
            BACKUP.backup_now()
            return mo.callout(mo.md(f"Backup saved to `{BACKUP.repo}`."), kind="success")
        if bk_restore.value:
            BACKUP.restore_latest()
            return mo.callout(mo.md(f"Database restored from `{BACKUP.repo}/latest.sqlite`. Reload the chat window "
                                    f"(pick the chat again in the sidebar)."), kind="success")
    except Exception as e:
        return mo.callout(mo.md(f"Failed: {e}"), kind="danger")
    return mo.md(f"_Automatic backup to `{BACKUP.repo}` is on, every {BACKUP.interval // 60} minutes when something changed._")


_backup_act()
