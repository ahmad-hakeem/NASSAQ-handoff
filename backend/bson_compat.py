"""
Compatibility stubs for bson/pymongo types used in the codebase.
These are no-op replacements now that MongoDB has been replaced with PostgreSQL.
"""


class ObjectId:
    def __init__(self, oid=None):
        self._id = str(oid) if oid else None

    def __str__(self):
        return self._id or ""

    def __repr__(self):
        return f"ObjectId('{self._id}')"

    def __eq__(self, other):
        if isinstance(other, ObjectId):
            return self._id == other._id
        return self._id == str(other)

    def __hash__(self):
        return hash(self._id)

    @staticmethod
    def is_valid(oid):
        return isinstance(oid, str) and len(oid) >= 12


class UpdateOne:
    def __init__(self, filter_dict, update_dict, upsert=False):
        self.filter = filter_dict
        self.update = update_dict
        self.upsert = upsert
