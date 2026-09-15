class Rule:
    """Stands in for qubesadmin.firewall.Rule."""

    def __init__(self, rule, action=None, dsthost=None, proto=None):
        self.action = action
        self.dsthost = dsthost
        self.proto = proto
