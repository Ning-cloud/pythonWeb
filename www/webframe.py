#!/usr/bin/env python3
#-*- coding: utf-8 -*-

__author__ = 'Jerome'

#inspect模块用于收集python对象的信息，可以获取类或函数的参数的信息，源码，解析堆栈，对对象进行类型检查等等
import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web
from apis import APIError


def get(path): #接受装饰器参数
    '''
    define decorator @get('/path')
    '''
    def decorator(func): #接受被包装函数
        @functools.wraps(func) #wrapper.__name__ = func.__name__
        def wrapper(*args,**kw): #接受包装函数的参数
            return func(*args,**kw)
        wrapper.__method__='GET'
        wrapper.__route__=path
        return wrapper
    return decorator

def post(path):
    '''
    define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps
        def wrapper(*args,**kw):
            func(*args,**kw)
        wrapper.__method__='POST'
        wrapper.__route__=path
        return wrapper
    return decorator

def get_required_kw_args(fn):
    '''
    找到处理函数中没有默认值的命名关键字参数（只出现在*或*args之后）,返回参数名字的tuple
    '''
    args=[]
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    '''
    找到处理函数的所有命名关键字参数（只出现在*或*args之后），返回参数名字的tuple
    '''
    args=[]
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    '''
    检查处理函数是否有命名关键字参数（只出现在*或*args之后）
    '''
    params=inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
    return False

def has_var_kw_arg(fn):
    '''
    检查处理函数是否有关键字参数（对应于python的**kw）
    '''
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    '''
    检查是否有request参数，如果有位置是否正确
    '''
    sig=inspect.signature(fn)
    params=sig.parameters
    found=False
    for name, param in params.items():
        if name == 'request':
            found=True
            continue
        #VAR_POSITIONAL对应与python中的*args
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__,str(sig)))
    return found

class RequestHandler(object):
    '''
    从url处理函数fn中分析出需要接受的参数，从request中取出必要的参数，调用URL函数，结果转换成web.Response对象
    '''
    def __init__(self,app,fn):
        self._app=app
        self._func=fn
        #为True的情况 1.只有一个名为request的参数 2. 离*args，*，**kw参数最近
        self._has_request_arg=has_request_arg(fn)
        self._has_var_kw_arg=has_var_kw_arg(fn)
        self._has_named_kw_args=has_named_kw_args(fn)
        #所有的命名关键字参数tuple
        self._named_kw_args=get_named_kw_args(fn)
        #没有默认值的命名关键字参数tuple
        self._required_kw_args=get_required_kw_args(fn)
    
    '''
    aiohttp规定add_route传入的url处理函数handler只有一个参数request，由aiohttp传入，和一个Response的返回值
    访问url时，由aiohttp调用对应的handler，再有RequestHandler调用最终的处理函数(用@get或@post标注的函数)

    位置参数 带有默认值的位置参数 可变参数 命名关键字参数 带有默认值的命名关键字参数 关键字参数
    url处理函数的参数情况
        1. 查询参数
            @get('/api/comments')
            def api_comments(*, page='1'):
                pass
        2. 带参数的URL/blog/{id}
            @get('/blog/{id}')
            def get_blog(id):
                pass
    '''
    async def __call__(self,request):
        kw = None
        #*后的参数和关键字参数
        logging.info('begin assemble url handler parameter.')
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
            logging.info('kw的内容是: %s' % str(kw))
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
    '''
    注册请求静态文件url与文件路径的映射
    '''
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/',path)
    logging.info('add static %s => %s' % ('/static/',path))

        
def add_route(app,fn):
    '''
    添加url和处理函数的映射
    '''
    method = getattr(fn,'__method__',None)
    path = getattr(fn,'__route__',None)
    if path is None or method is None:
        raise ValueError('@get or @ post not defined in %s' % str(fn))
    #封装成异步函数
    if not asyncio.iscoroutine(fn) and not inspect.isgeneratorfunction(fn):
        fn=asyncio.coroutine(fn)
    logging.info('add route %s %s ==> %s(%s)' % (method,path,fn.__name__,', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method,path,RequestHandler(app,fn))

def add_routes(app,module_name):
    '''
    自动扫描 注册url处理函数
    modelule_name
        1. handlers
        2. www.handlers
    '''
    n = module_name.rfind('.')
    logging.info('automatic register url handler in Module: %s' % module_name)
    if n == -1:
        mod=__import__(module_name,globals(),locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n],globals(),locals(),[name]),name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod,attr)
        if callable(fn):
            method=getattr(fn,'__method__',None)
            path=getattr(fn,'__route__',None)
            if method and path:
                add_route(app,fn)
        
