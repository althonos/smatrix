import subprocess


class QosConfiguration(object):

    @classmethod
    def _query_sacctmgr(cls, binary="sacctmgr"):
        args = [binary, "-P", "list", "qos"]
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        proc.check_returncode()
        stdout = proc.stdout.decode('ascii').splitlines()
        headers = stdout[0].split("|")
        values = [dict(zip(headers, line.split("|"))) for line in stdout[1:]]
        return { qos['Name']: qos for qos in values }

    def __init__(self, qos):
        # get the QOS setting from the slurm account manager
        result = self._query_sacctmgr()
        if qos in result:
            self._raw = result[qos]
        else:
            raise ValueError("unknown QOS value: {}".format(qos))

        # parse the values obtained with the query to sacctmgr
        self.priority = int(self._raw['Priority']) if self._raw['Priority'] else 0
        self.max_jobs_per_account = int(self._raw['MaxJobsPA']) if self._raw['MaxJobsPA'] else None
        self.max_jobs_per_user = int(self._raw['MaxJobsPU']) if self._raw['MaxJobsPU'] else None
        self.max_submit_per_account = int(self._raw['MaxSubmitPA']) if self._raw['MaxSubmitPA'] else None
        self.max_submit_per_user = int(self._raw['MaxSubmitPU']) if self._raw['MaxSubmitPU'] else None
