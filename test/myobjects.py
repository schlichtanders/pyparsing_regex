class Count(object):
    """ future-like counting object
    
    The first time the attribute ``value`` is accessed, it gets computed by counting onwards from the total_count
    """
    total_count = 0
    
    @staticmethod
    def reset(total_count=0):
        Count.total_count = total_count
        
    def __init__(self, _value=None):
        self._value = _value
    
    def __copy__(self):
        return Count(self._value)
    
    @property
    def value(self):
        if self._value is None:
            self._value = Count.total_count
            Count.total_count += 1
        return self._value
    
    def eval(self):
        self.value
        return self
        
    def __str__(self):
        return "?" if self._value is None else str(self._value)
    
    def __repr__(self):
        return str(self)