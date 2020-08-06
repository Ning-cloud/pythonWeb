#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
JSON API definition
'''

import json, logging, functools, inspect

class APIError(Exception):
    '''
    the base API error contains data(optional), message(optional), error(required)
    '''
    def __init__(self,error,data='',message=''):
        super(APIException,self).__init__(message)
        self.error=error
        self.data=data
        self.message=message
    
class APIValueError(APIError):
    '''
    indicate the input data has error. the data specifies the error field of input form
    '''
    def __init__(self,field,message=''):
        super(APIValueError,self).__init__('value:invalid',field,message)

class APIResourceNotFoundError(APIError):
    '''
    indicate the resource not found. the data specified the resource name
    '''
    def __init__(self,field,message=''):
        super().__init__('value:notfound',field,message)

class APIPermissionError(APIError):
    '''
    indicate the api has no permission
    '''
    def __init__(self,message=''):
        super().__init__('permission:forbidden','permission',message)