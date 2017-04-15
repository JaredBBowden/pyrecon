""" Module containing backend methods for PyRECONSTRUCT's mergetool.
"""
from collections import defaultdict
from copy import deepcopy

import numpy
from PIL import Image

from .models import Base, Contour, ContourMatch
from .utils import is_contacting, is_exact_duplicate, is_potential_duplicate


def create_database(engine):
    """ Uses the provided engine to create the database.
    """
    Base.metadata.create_all(engine)


def get_section_contours_from_database(section_number):
    """ Returns the db.Contour objects in the provided section_number.
    """
    return session.query(
        Contour
    ).filter(
        Contour.section == section_number
    ).all()


def get_matches(match_type=None):
    """ Returns db.ContourMatch objects.

        Can provide a match_type to return only those of a particular match_type.
    """
    query = session.query(
        ContourMatch.id1,
        ContourMatch.id2,
        ContourMatch.match_type
    )
    if match_type:
        query = query.filter(
            ContourMatch.match_type == match_type
        )
    return query.all()


def _create_db_contours_from_pyrecon_section(section):
    """ Returns db.Contour objects for contours in a pyrecon.Section.
    """
    db_contours = []
    for i, pyrecon_contour in enumerate(section.contours):
        db_contour = Contour(
            section=section.index,
            index=i
        )
        db_contours.append(db_contour)
    return db_contours


def load_db_contours_from_pyrecon_section(session, section):
    """ From a pyrecon.Section object, inster db.Contour entities into the db.
    """
    db_contours = _create_db_contours_from_pyrecon_section(section)
    session.add_all(db_contours)
    session.commit()
    return db_contours


def _create_db_contourmatch_from_db_contours_and_pyrecon_section(db_contour_A, db_contour_B,
                                                                 section):
    """ Returns a db.ContourMatch from 2 db.Contours and a pyrecon.section, or None.
    """
    pyrecon_contour_a = section.contours[db_contour_A.index]
    pyrecon_contour_b = section.contours[db_contour_B.index]
    if pyrecon_contour_a.name != pyrecon_contour_b.name:
        return None
    elif pyrecon_contour_a.shape.type != pyrecon_contour_b.shape.type:
        return None

    shape_a = pyrecon_contour_a.shape
    shape_b = pyrecon_contour_b.shape
    try:
        if (pyrecon_contour_a.points == pyrecon_contour_b.points) and \
           (pyrecon_contour_a.transform != pyrecon_contour_b.transform):
            match_type = "potential_realigned"
            return ContourMatch(
                id1=db_contour_A.id,
                id2=db_contour_B.id,
                match_type=match_type
            )
        elif not is_contacting(shape_a, shape_b):
            return None
        elif is_exact_duplicate(shape_a, shape_b):
            match_type = "exact"
            return ContourMatch(
                id1=db_contour_A.id,
                id2=db_contour_B.id,
                match_type=match_type
            )
        elif is_potential_duplicate(shape_a, shape_b):
            match_type = "potential"
            return ContourMatch(
                id1=db_contour_A.id,
                id2=db_contour_B.id,
                match_type=match_type
            )
    except Exception as e:
        import pdb; pdb.set_trace()
        print("{}".format(e))
    return None


def _create_db_contourmatches_from_db_contours_and_pyrecon_section(db_contours, section):
    """ Returns db.ContourMatch objects for contours in a pyrecon.Section.
    """
    matches = []
    for idx, db_contour_A in enumerate(db_contours):
        contA = section.contours[db_contour_A.index]
        for idy, db_contour_B in enumerate(db_contours):
            contB = section.contours[db_contour_B.index]
            if idx >= idy:
                continue
            match = _create_db_contourmatch_from_db_contours_and_pyrecon_section(
                db_contour_A, db_contour_B, section)
            if match:
                matches.append(match)
    return matches


def load_db_contourmatches_from_db_contours_and_pyrecon_section(session, db_contours, section):
    """ From a pyrecon.Section object, insert db.ContourMatch entities into the db.
    """
    db_contourmatches = _create_db_contourmatches_from_db_contours_and_pyrecon_section(
        db_contours, section)
    session.add_all(db_contourmatches)
    session.commit()
    return db_contourmatches


# =======================
# TODO: cleanup below vvv
# =======================
def _retrieve_matches_for_db_contour_id(session, db_contour_id):
    """ Returns all ContourMatch objects that match the provided db_contour_id.
    """
    return session.query(
        ContourMatch
    ).filter(
        ContourMatch.id1 == db_contour_id
    ).all()


def group_section_matches(session, section_number):
    grouped = defaultdict(lambda: defaultdict(set))
    for id_ in session.query(Contour.id).filter(Contour.section==section_number).all():
        id_ = id_[0]
        matches = _retrieve_matches_for_db_contour_id(session, id_)
        grouped[id_] = defaultdict(set)
        for m in matches:
            grouped[m.id1][m.match_type].add(m.id2)
    return grouped


def prepare_contour_dict_for_frontend(contour, db_id, section, keep=True):
    """ Converts a contour to a dict expected by the frontend.
    """
    #converting to pixels
    contour_copy = deepcopy(contour)
    contour_copy.points = list(map(tuple, contour_copy.transform._tform.inverse(
        numpy.asarray(contour_copy.points)/section.images[0].mag)))
    nullPoints = contour_copy.shape.bounds

    flipVector = numpy.array([1, -1])
    im = Image.open(section.images[0]._path + "/{}".format(section.images[0].src))
    imWidth, imHeight = im.size
    translationVector = numpy.array([0, imHeight])

    if contour_copy.shape.type == "Polygon":
        transformedPoints = list(map(tuple, translationVector+(numpy.array(list(contour_copy.shape.exterior.coords))*flipVector)))

    else:
        x, y = contour_copy.shape.xy
        x = list(x)
        y = list(y)
        coords = zip(x,y)
        transformedPoints = list(map(tuple, translationVector+(numpy.array(list(coords))*flipVector)))
    contour_copy.points = transformedPoints

    #cropping
    minx, miny, maxx, maxy = contour_copy.shape.bounds
    x = minx-100
    y = miny - 100
    width = maxx-x+100
    height = maxy-y+100
    rect = [x, y, width, height]
    cropVector = numpy.array([x,y])
    croppedPoints = list(map(tuple, numpy.array(contour_copy.points)-cropVector))

    return {
        'name': contour.name,
        'points': contour.points,
        'image': section.images[0]._path + "/{}".format(section.images[0].src),
        'db_id': db_id,
        'nullpoints': nullPoints,
        'rect': rect,
        'croppedPoints': croppedPoints,
        'keepBool' : keep
    }


def prepare_unique_query(session, section):
    """ Return a query for unique db contour ids in a section.
    """
    id1_matches_query = session.query(
        ContourMatch.id1
    ).filter(
        ContourMatch.id1.in_(
            session.query(
                Contour.id
            ).filter(
                Contour.section == section.index
            )
        )
    )
    id2_matches_query = session.query(
        ContourMatch.id2
    ).filter(
        ContourMatch.id2.in_(
            session.query(
                Contour.id
            ).filter(
                Contour.section == section.index
            )
        )
    )
    matched_ids_union = id1_matches_query.union(id2_matches_query)
    return session.query(Contour.id).filter(
        Contour.id.notin_(matched_ids_union),
        Contour.section == section.index
    )


def prepare_frontend_payload(session, section, grouped):
    section_matches = {
        "section": section.index,
        "exact": [],
        "potential": [],
        "potential_realigned": [],
        "unique": []
    }

    # TODO: clean and test this VVV
    for contour_A_id, match_dict in grouped.items():
        db_contour_A = session.query(Contour).get(contour_A_id)
        reconstruct_contour_a = section.contours[db_contour_A.index]
        main_contour_data = prepare_contour_dict_for_frontend(
            reconstruct_contour_a,
            contour_A_id,
            section,
            keep=True
        )

        for match_type, matches in match_dict.items():
            # matchNum = len(matches)
            # if (match_type == 'potential') or (match_type == 'potential_realigned'):
            #     matchCounter = [1]*(matchNum+1)
            # elif (match_type == 'exact'):
            #     matchCounter = [1]
            #     matchCounter += [0]*(matchNum)

    #        match_list = [list(matchCounter), main_contour_data]
            match_list = [main_contour_data]
            for match_id in matches:
                db_contour_B = session.query(Contour).get(match_id)
                reconstruct_contour_b = section.contours[db_contour_B.index]
                if (match_type == 'potential') or (match_type == 'potential_realigned'):
                    keepBool = True
                elif (match_type == 'exact'):
                    keepBool = False
                match_dict = prepare_contour_dict_for_frontend(
                    reconstruct_contour_b,
                    match_id,
                    section,
                    keep=keepBool
                )
                match_list.append(match_dict)
            section_matches[match_type].append(match_list)

    # Add uniques to payload
    unique_ids_query = prepare_unique_query(session, section)
    for unique_id in unique_ids_query:
        db_contour_unique = session.query(Contour).get(unique_id)
        unique_reconstruct_contour = section.contours[db_contour_unique.index]
        unique_dict = prepare_contour_dict_for_frontend(
            unique_reconstruct_contour,
            unique_id,
            section,
            keep=True
        )
        section_matches['unique'].append([unique_dict])
    return section_matches