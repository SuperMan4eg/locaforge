from locaforge.app import bootstrap


def test_self_test_exercises_project_lifecycle_and_releases_temporary_files() -> None:
    bootstrap.run_self_test()
