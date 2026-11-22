from flask import Blueprint, request

from app.admin.core.security import ApiError, ok, require_role

from . import repository as repo

bp = Blueprint('admin_farms', __name__, url_prefix='/api/admin')
PLOT_FILTERS = ('farm_id', 'owner_id', 'status', 'crop_type')


def _found(row, message):
    if row is None:
        raise ApiError('not_found', message, 404)
    return row


@bp.get('/farms')
@require_role()
def list_farms():
    items, page, size, total = repo.list_farms(request.args.get('owner_id'), request.args.get('q'))
    return ok(items=items, page=page, page_size=size, total=total)


@bp.get('/farms/<identifier>')
@require_role()
def get_farm(identifier):
    return ok(farm=_found(repo.farm(identifier), 'Không tìm thấy nông trại.'), plots=repo.plots_of_farm(identifier))


@bp.get('/plots')
@require_role()
def list_plots():
    filters = {k: request.args[k] for k in PLOT_FILTERS if request.args.get(k)}
    items, page, size, total = repo.list_plots(filters)
    return ok(items=items, page=page, page_size=size, total=total)


@bp.get('/plots/<identifier>')
@require_role()
def get_plot(identifier):
    return ok(plot=_found(repo.plot(identifier), 'Không tìm thấy ruộng.'), seasons=repo.seasons_of_plot(identifier))


@bp.get('/seasons/<identifier>')
@require_role()
def get_season(identifier):
    season = _found(repo.season(identifier), 'Không tìm thấy mùa vụ.')
    return ok(season=season, devices=repo.season_devices(identifier), revisions=repo.season_revisions(identifier),
              cultivation_profile=repo.season_profile(identifier))
