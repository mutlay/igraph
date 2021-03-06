import web
import re
import os.path
from web import websafe
from itertools import izip

if os.path.exists("../db/nexus.db"):
    dbfile='../db/nexus.db'
elif os.path.exists("../db/test.db"):
    dbfile='../db/test.db'
db = web.database(dbn='sqlite', db=dbfile)

def get_list_tagged_as(tagname, operator="or", order="date", limit=10, 
                       offset=0):
    ord={ 'date': 'd.date DESC, d.id DESC',
          'name': 'd.name',
          'popularity': 'd.downloads DESC, d.date DESC, d.id DESC' }
    tagstr=["'%s'" % websafe(t) for t in tagname]
    tagstr='(' + ",".join(tagstr) + ")"
    if operator=="or":
        table='dataset d, dataset_tag dt, tag t, network n'
        what='''DISTINCT d.id id, d.sid sid, d.name name,
                         d.description description,
                         d.shortdescription shortdescription,
                         d.licence licence, d.date date, 
                         d.source source,
                         COUNT(n.vertices) nnets,
                         MIN(n.vertices) minv, MAX(n.vertices) maxv, 
                         MIN(n.edges) mine, MAX(n.edges) maxe'''
        where='''d.id=dt.dataset 
                 AND n.dataset=d.id
                 AND dt.tag=t.id 
                 AND t.tag IN %s''' % tagstr
        group="d.id"
        res=db.select(table, what=what, where=where, order=ord[order],
                      offset=offset, limit=limit, group=group)
        count=list(db.select(table, what='COUNT(DISTINCT d.id) c',
                             where=where))[0].c
    else:
        table="dataset d, network n"
        what='''d.id id, d.sid sid, d.name name,
                d.description description, 
                d.shortdescription shortdescription,
                d.licence licence, d.date date, d.source source,
                COUNT(n.vertices) nnets,
                MIN(n.vertices) minv, MAX(n.vertices) maxv, 
                MIN(n.edges) mine, MAX(n.edges) maxe'''
        where='''d.id IN (SELECT id FROM 
                                    (SELECT dt.dataset id, COUNT(*) count
                                     FROM dataset_tag dt, tag t
                                     WHERE dt.tag=t.id AND t.tag IN %s
                                     GROUP BY dt.dataset)
                                 WHERE count=%s)
                 AND n.dataset=d.id
                 ''' % (tagstr, len(tagname))
        group="d.id"
        res=db.select(table, what=what, where=where, order=ord[order],
                      offset=offset, limit=limit, group=group)
        count=list(db.select(table, what='COUNT(*) c', where=where))[0].c
    
    return list(res), count

def get_list_of_datasets(ids=None, order="date", limit=10, offset=0):

    ord={ 'date': 'd.date DESC, d.id DESC',
          'name': 'd.name',
          'popularity': 'd.downloads DESC, d.date DESC, d.id DESC' }

    if ids is None:
        where=''
        where2=None
    else:
        ids=[str(i) for i in ids]
        where='AND d.id IN (' + ','.join(ids) + ')'
        where2='id IN (' + ','.join(ids) + ')'

    count=list(db.select('dataset', what='COUNT(id) count', 
                         where=where2))[0].count

    res=db.query('''SELECT d.id id, d.sid sid, d.name name, 
                           d.description description, 
                           d.shortdescription shortdescription,
                           d.licence licence, d.date date, d.source source,
                           COUNT(n.vertices) nnets,
                           MIN(n.vertices) minv, MAX(n.vertices) maxv, 
                           MIN(n.edges) mine, MAX(n.edges) maxe
                    FROM dataset d, network n
                    WHERE n.dataset=d.id %s
                    GROUP BY d.id
                    ORDER BY %s
                    LIMIT %s 
                    OFFSET %s''' % (where, ord[order], 
                                    int(limit), int(offset)))
    res=list(res)
    return res, count

def get_dataset_ids():
    return list(db.select('dataset', what='id', order='id'))

def get_tags(id):
    return db.query('''SELECT t.id, t.tag 
                       FROM tag t, dataset_tag d
                       WHERE t.id=d.tag AND dataset=$id
                       ORDER BY t.tag''', 
                    vars={'id': id})

def get_dataset(id):
    return db.query('''SELECT d.id id, d.sid sid, d.name name, 
                              d.description description, 
                              d.shortdescription shortdescription,
                              l.id licence,
                              l.name licence_name,
                              l.link licence_url,
                              d.date date, d.source source,
                              COUNT(n.vertices) nnets,
                              MIN(n.vertices) minv, MAX(n.vertices) maxv, 
                              MIN(n.edges) mine, MAX(n.edges) maxe
                       FROM dataset d, licence l, network n
                       WHERE d.licence=l.id
                         AND d.id=n.dataset
                         AND d.id=$id''',
                    vars={'id': id})

def delete_dataset(id):
    db.delete('dataset', where='id=%s' % int(id))
    db.delete('network', where='dataset=%s' % int(id))
    db.delete('dataset_citation', where='dataset=%s' % int(id))
    db.delete('dataset_tag', where='dataset=%s' % int(id))
    db.delete('metadata', where='dataset=%s' % int(id))

def delete_network(dataset, id):
    where='dataset=%s AND id=%s' % (websafe(dataset), websafe(id))
    db.delete('network', where=where)

def get_dataset_filename(id):
    res=list(db.select('dataset', what='sid', where='id=%s' % websafe(id)))
    return res[0].sid

def whatsnew():
    return db.select('dataset', limit=5, order="date DESC, id DESC")

def datatags():
    return db.query('''SELECT t.tag tag, COUNT(*) count
                       FROM dataset_tag dt, tag t 
                       WHERE dt.tag=t.id 
                       GROUP BY dt.tag
                       ORDER BY count DESC;''')

def get_formats():
    return list(db.select('format'))

def get_papers(id):
    return db.query('''SELECT c.citation citation
                       FROM citation c, dataset_citation d
                       WHERE c.id=d.citation 
                       AND d.dataset=%s''' % websafe(id))

def get_format(name):
    return db.select('format', where="name='%s'" % websafe(name))

def get_licences(what=None):
    return db.select('licence', what=what, order="name")

def new_dataset(**args):
    return db.insert('dataset', seqname='id', **args)

def new_network(**args):
    db.insert('network', seqname=None, **args)

def new_citation(dataset, citation):
    ex=list(db.select('citation', what='id', where='citation=$citation',
                      vars={ 'citation': citation}))
    if not ex:        
        citid=db.insert('citation', seqname=None, citation=citation)
    else:
        citid=ex[0].id
    db.insert('dataset_citation', seqname='id', 
              dataset=dataset, citation=citid)

def new_dataset_tag(dataset, tag):
    ex=db.select('tag', what='id', where='tag=$tag', 
                 vars={ 'tag': tag })
    ex=[e for e in ex]
    if not ex:
        tagid=db.insert('tag', seqname='id', tag=tag)
    else:
        tagid=ex[0].id
    db.insert('dataset_tag', seqname=None, dataset=dataset, tag=tagid)

def delete_tags(id):
    db.delete('dataset_tag', where='dataset=%s' % websafe(id))    

def new_licence(**args):
    return db.insert('licence', seqname="id", **args)

def update_dataset(id, sid, name, shortdescription,
                   description, licence, source, papers):

    db.update('dataset', where='id=%s' % int(id), sid=sid, name=name,
              shortdescription=shortdescription,
              description=description, licence=int(licence), 
              source=source)

    db.delete('dataset_tag', where='dataset=%s' % int(id))

    db.delete('dataset_citation', where='dataset=%s' % int(id))
    for p in papers:
        new_citation(id, p)
    
    return True

def update_network(dataset, id, **args):
    where='dataset=%s AND id=%s' % (websafe(dataset), websafe(id))
    db.update('network', where=where, **args)
    return True

def get_username(openid=None):
    if not openid:
        openid=web.webopenid.status()
    user=db.select('user', what='name', 
                   where="openid='%s'" % websafe(openid))
    if user:
        return [u for u in user][0].name
    else:
        return None

def get_licence(id):
    return db.select('licence', where="id='%s'" % int(id))

def update_licence(id, **args):
    db.update('licence', where='id=%s' % int(id), **args)
    return True

def get_metadata(id):
    what="DISTINCT dataset, type, name, description, datatype, network"
    res=db.select('metadata', what=what,
                  where='dataset=%s' % int(id), order="type")
    return list(res)

def delete_meta(id, type, name):
    res=db.delete('metadata', where="dataset=%s AND type='%s' AND name='%s'" %
                  (websafe(id), websafe(type), websafe(name)))

def update_meta(id, type, name, **args):
    res=db.update('metadata', where="dataset=%s AND type='%s' AND name='%s'" %
                  (websafe(str(id)), websafe(type), websafe(name)),
                  type=type, name=name, **args)

def add_meta(id, type, name, **args):
    res=db.insert('metadata', dataset=id, type=type, name=name,
                  **args)

def get_blog(ids=None, unpublished=False):
    if ids is None:
        limit=5
        order='date DESC'
        where='1=1'
    else:
        limit=None
        order='id'
        where="id in (" + ",".join(ids) + ")"

    if not unpublished:
        where=where + " AND published=1"

    return list(db.select('blog', limit=limit, order=order, where=where))

def new_blog_entry(**args):
    return db.insert('blog', seqname='id', **args)

def update_blog(id, **args):
    db.update('blog', where='id=%s' % int(id), **args)

def increase_downloads(id):
    db.query('''UPDATE dataset SET downloads=downloads+1 WHERE id=%s''' % \
                 int(id))

def get_totals():
    res=db.select('dataset', 
                  what='COUNT(*) AS count, SUM(downloads) AS downloads')
    return list(res)[0]

def get_format_extensions():
    res=db.select('format', what='name,extension')
    return dict( (f.name,f.extension) for f in res )

def get_format_extension(format):
    res=db.select('format', what='extension', 
                  where="name='%s'" % websafe(format))
    return list(res)[0].extension

def regexp(expr, item):
    return int(re.search(expr, item, re.IGNORECASE) is not None)

def install_regexp():
    db._getctx().db.create_function('REGEXP', 2, regexp)

## TODO: search in other fields: publication, metadata, number of vertices
def do_search_query(tokens, offset=0, limit=10):

    tokens=[ websafe(t) for t in tokens ]

    if len(tokens)==0:
        return range(1, get_totals().count+1)

    install_regexp()

    searchfields=['name', 'shortdescription', 'description']

    recs=[]
    i=0
    while i < len(tokens):
        if tokens[i] == '-' and i+1 < len(tokens) and tokens[i+1][-1] != ':':
            recs.append( (None, tokens[i+1], True) )
            i += 2
        elif tokens[i] == '-' and i+2 < len(tokens) and \
                tokens[i+1][-1] == ':':
            recs.append( (tokens[i+1][:-1], tokens[i+2], True) )
            i += 3
        elif tokens[i] == '-':
            i += 1
        elif tokens[i][-1] == ':' and i+1 < len(tokens):
            if tokens[i][:-1] in searchfields:
                recs.append( (tokens[i][:-1], tokens[i+1]) )
                i += 2
            else:
                recs.append( (None, tokens[i+1]) )
                i += 2
        else:
            recs.append( (None, tokens[i]) )
            i += 1

    clause="%s %s REGEXP '\\b%s\\b'"

    def allfields(rec):
        if len(rec)>=3 and rec[2]:
            n='NOT'
            op=' AND '
        else:
            n=''
            op=' OR '
        return '(' + op.join([ clause % (f,n,rec[1]) 
                               for f in searchfields]) + ')'

    def term(rec):
        if rec[0] is None:
            return allfields(rec)
        else:
            if len(rec)>=3 and rec[2]:
                n='NOT'
            else:
                n=''
            return clause % (rec[0], n, rec[1])

    where=' AND '.join([ term(r) for r in recs ])
    
    res=db.select('dataset', what='id', where=where)
    return [r.id for r in res]

def get_id_from_sid(sid):
    res=list(db.select('dataset', what='id', 
                       where="sid='%s'" % websafe(sid)))
    if len(res)==0:
        return None
    else:
        return str(res[0].id)

def get_networks(dataset):
    return list(db.select('network', where='dataset=%s' % websafe(dataset),
                          order="id"))

def get_net_id_from_sid(dataset, sid):
    where="dataset=%s AND sid='%s'" % (websafe(dataset), websafe(sid))
    res=list(db.select('network', what='id', where=where))
    if len(res)==0:
        return None
    else:
        return str(res[0].id)    

def get_net_sid_from_id(dataset, id):
    where="dataset=%s AND id=%s" % (websafe(dataset), websafe(id))
    res=list(db.select('network', what='sid', where=where))
    if len(res)==0:
        return None
    else:
        return str(res[0].sid)

def get_networks(id):
    res=db.select('network', where='dataset=%s' % websafe(str(id)), 
                  order='id')
    return list(res)

def get_sids():
    res=db.select('dataset', what='id,sid')
    return list(res)

def update_filesize(id, format, size):
    try:
        db.insert('filesize', dataset=int(id), format=websafe(format), 
                  size=int(size))
    except:
        db.update('filesize', where='dataset=%s AND format="%s"' %
                  (int(id), websafe(format)), size=size)
    return True
