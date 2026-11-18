from ..services import privacy
class PrivacyController:
    list=staticmethod(privacy.list_studies)
    create=staticmethod(privacy.create_study)
    cancel=staticmethod(privacy.cancel_study)
    account=staticmethod(privacy.account_view)
    @staticmethod
    def get(db,id):return privacy.study_detail(db,id)
