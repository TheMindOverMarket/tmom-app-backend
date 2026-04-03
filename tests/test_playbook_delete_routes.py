from sqlmodel import Session, select

from app.models import (
    Condition,
    Playbook,
    Rule,
    Session as SessionModel,
    SessionEvent,
    SessionEventType,
    User,
)


def test_delete_playbook_cascades_related_records(client, db_session: Session, test_user: User):
    playbook = Playbook(
        user_id=test_user.id,
        name="Delete Me",
        original_nl_input="Delete this playbook",
    )
    db_session.add(playbook)
    db_session.flush()

    rule = Rule(playbook_id=playbook.id, name="Entry Rule")
    db_session.add(rule)
    db_session.flush()

    condition = Condition(rule_id=rule.id, metric="price", comparator=">", value="100")
    db_session.add(condition)

    session = SessionModel(user_id=test_user.id, playbook_id=playbook.id)
    db_session.add(session)
    db_session.flush()

    event = SessionEvent(
        session_id=session.id,
        type=SessionEventType.SYSTEM,
        event_data={"message": "created for delete test"},
    )
    db_session.add(event)
    db_session.commit()

    response = client.delete(f"/playbooks/{playbook.id}")
    assert response.status_code == 204

    assert db_session.get(Playbook, playbook.id) is None
    assert db_session.exec(select(Rule).where(Rule.playbook_id == playbook.id)).all() == []
    assert db_session.exec(select(Condition).where(Condition.rule_id == rule.id)).all() == []
    assert db_session.exec(select(SessionModel).where(SessionModel.playbook_id == playbook.id)).all() == []
    assert db_session.exec(select(SessionEvent).where(SessionEvent.session_id == session.id)).all() == []


def test_delete_all_playbooks_only_clears_target_users_library(client, db_session: Session, test_user: User):
    other_user = User(email="second@example.com")
    db_session.add(other_user)
    db_session.flush()

    target_playbook = Playbook(
        user_id=test_user.id,
        name="Delete All Target",
        original_nl_input="Delete all for this user",
    )
    other_playbook = Playbook(
        user_id=other_user.id,
        name="Keep Me",
        original_nl_input="Other user's playbook",
    )
    db_session.add(target_playbook)
    db_session.add(other_playbook)
    db_session.commit()

    response = client.delete(f"/playbooks/users/{test_user.id}/playbooks")
    assert response.status_code == 204

    assert db_session.get(Playbook, target_playbook.id) is None
    assert db_session.get(Playbook, other_playbook.id) is not None
