import gc


class RuntimeMemoryService:
    def cancel_job(self, root, owner, attr_name):
        job_id = getattr(owner, attr_name, None)
        if not job_id:
            return False
        try:
            root.after_cancel(job_id)
        except Exception:
            pass
        setattr(owner, attr_name, None)
        return True

    def cancel_jobs(self, root, owner, attr_names):
        for attr_name in attr_names:
            self.cancel_job(root, owner, attr_name)

    def release_analysis_references(self):
        gc.collect()

    def join_thread(self, thread, timeout=None):
        if thread is None:
            return True
        if not thread.is_alive():
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

