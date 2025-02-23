'''
	Scripts to train base classifiers in a nested cross-validation structure.
	See README.md for detailed information.
	@author: Yan-Chak Li, Jamie Bennett, Linhua Wang
'''
from os.path import isdir
from os import listdir
import argparse
from itertools import product
from os import system
import os
from os.path import abspath, dirname, exists
from sys import argv
from common import load_properties, read_arff_to_pandas_df, load_properties_sk
from time import time
import generate_data
import numpy as np
from importlib.util import spec_from_file_location, module_from_spec

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def create_pseudoTestdata(data_dir, feat_folders, original_dir):
    new_feat_folders = []

    os.system('cp {} {}'.format(os.path.join(original_dir, 'define_base_predictors.py'),
                                data_dir))
    os.system('cp {} {}'.format(os.path.join(original_dir,'sk.properties'),
                                data_dir))
    for ff in feat_folders:
        feat_df = read_arff_to_pandas_df(os.path.join(ff, 'data.arff'))
        feat_df_drop_idx = feat_df.drop(columns=['fold', 'seqID', 'cls'])
        real_val_cols = []
        feature_cols = feat_df_drop_idx.columns
        real_val_cols = []
        for i_col in feature_cols:
            if len(feat_df_drop_idx[i_col].unique()) > 2:
                real_val_cols.append(i_col)
        feat_df.loc[:, 'fold'] = 0
        # create 20 pseudo test entries
        df_shape = feat_df.shape
        number_of_real_col = len(real_val_cols)
        for i in range(20):
            ri = i + df_shape[0]
            feat_df.loc[ri] = np.random.binomial(size=df_shape[1], n=1, p=0.5)
            # number_of_real_col = len(real_val_cols)
            # feat_df.loc[ri] = np.random.randn(number_of_real_col)
            feat_df.loc[ri, real_val_cols] = np.random.randn(number_of_real_col)
            feat_df.loc[ri, 'fold'] = 1
            feat_df.loc[ri, 'seqID'] = i
            if (i % 2) == 0:
                c = 'pos'
            else:
                c = 'neg'
            feat_df.loc[ri, 'cls'] = c
        new_feat_dir = os.path.join(data_dir, ff.split('/')[-1])
        if not exists(new_feat_dir):
            os.mkdir(new_feat_dir)
            feat_df['fold'] = feat_df['fold'].astype(int)
            os.system('cp {} {}'.format(os.path.join(original_dir, 'define_base_predictors.py'),
                                        new_feat_dir))
            os.system('cp {} {}'.format(os.path.join(original_dir, 'sk.properties'),
                                        new_feat_dir))
            generate_data.convert_to_arff(feat_df, os.path.join(new_feat_dir,'data.arff'))
        new_feat_folders.append(new_feat_dir)
    return data_dir, new_feat_folders

if __name__ == "__main__":
    ### parse arguments
    parser = argparse.ArgumentParser(description='Feed some bsub parameters')
    parser.add_argument('--path', '-P', type=str, required=True, help='data path')
    parser.add_argument('--queue', '-Q', type=str, default='premium', help='LSF queue to submit the job')
    parser.add_argument('--node', '-N', type=str, default='16', help='number of node requested')
    parser.add_argument('--time', '-T', type=str, default='20:00', help='number of hours requested')
    parser.add_argument('--memory', '-M', type=str, default='20000', help='memory requested in MB')
    parser.add_argument('--hpc', type=str, default='minerva', help='parallelize either using minerva or GNU parallel')
    parser.add_argument('--fold', '-F', type=int, default=5, help='number of cross-validation fold')
    parser.add_argument('--rank', type=str2bool, default='False', help='getting attribute importance')
    # parser.add_argument('--create_rank_dir', type=str2bool, default='False', help='getting attribute importance')
    args = parser.parse_args()
    ### record starting time
    start = time()
    ### get the data path
    data_path = abspath(args.path)
    data_source_dir = data_path.split('/')[-2]
    data_name = data_path.split('/')[-1]
    working_dir = dirname(abspath(argv[0]))

    ### get scikit-learn properties from sk.properties
    p = load_properties_sk(data_path)
    bag_values = range(int(p['bagCount']))

    ### get the list of base predictors

    predictors_path = data_path + '/define_base_predictors.py'
    assert exists(predictors_path)
    bp_spec = spec_from_file_location('predictors', predictors_path)
    bp_module = module_from_spec(bp_spec)
    bp_spec.loader.exec_module(bp_module)
    predictors = bp_module.predictors
    classifiers = predictors.keys()
    print('Base Classifiers:', list(classifiers))

    ### get paths of the list of features
    fns = listdir(data_path)
    excluding_folder = ['analysis', 'feature_rank', '__pycache__']
    fns = [fn for fn in fns if not fn in excluding_folder]
    fns = [fn for fn in fns if not 'tcca' in fn]
    fns = [data_path + '/' + fn for fn in fns]
    feature_folders = [fn for fn in fns if isdir(fn)]

    if args.rank:
        feature_rank_path = os.path.join(data_path,'feature_rank')
        if not exists(feature_rank_path):
            os.mkdir(feature_rank_path)
        data_path, feature_folders = create_pseudoTestdata(feature_rank_path,
                                                           feature_folders,
                                                           original_dir=data_path,
                                                           # create_rank_dir=args.create_rank_dir,
                                                           )

    if 'foldAttribute' in p:
        df = read_arff_to_pandas_df(feature_folders[0] + '/data.arff')
        fold_values = list(df[p['foldAttribute']].unique())
    else:
        fold_values = range(int(p['foldCount']))
    id_col = p['idAttribute']
    label_col = p['classAttribute']
    jobs_fn = "temp_train_base_{}_{}.jobs".format(data_source_dir, data_name)
    job_file = open(jobs_fn, 'w')
    #if not args.hpc == 'minerva': # don't think we need this
        #job_file.write('module load python\n')

    def preprocessing(jf):
        all_parameters = list(product(feature_folders, classifiers, fold_values, bag_values))

        for parameters in all_parameters:
            project_path, classifier, fold, bag = parameters
            jf.write('python base_predictors_sk.py --parentDir {} --rootDir {} --currentFold {} --currentBag {} --classifierName {} --attr_imp_bool {}\n'.format(
                data_path, project_path, fold, bag, classifier, args.rank))

        if (not args.hpc == 'minerva') and (not args.hpc == 'parallel'):
            jf.write('python combine_individual_feature_preds.py %s %s\npython combine_feature_predicts.py %s %s\n' % (
                data_path, args.rank, data_path, args.rank))
        return jf

    job_file = preprocessing(job_file)
    job_file.close()

    ### submit to hpc if args.hpc == 'hpc'
    if args.hpc == 'minerva':
        lsf_fn = 'run_%s_%s.lsf' % (data_source_dir, data_name)
        fn = open(lsf_fn, 'w')
        fn.write(
            '#!/bin/bash\n#BSUB -J EI-%s\n#BSUB -P acc_pandeg01a\n#BSUB -q %s\n#BSUB -n %s\n#BSUB -sp 100\n#BSUB -W '
            '%s\n#BSUB -o %s.stdout\n#BSUB -eo %s.stderr\n#BSUB -R rusage[mem=20000]\n' % (
            data_name, args.queue, args.node, args.time, data_source_dir, data_source_dir))
        fn.write('module load python\nmodule load selfsched\n')
        fn.write('mpirun selfsched < {}\n'.format(jobs_fn))
        fn.write('python combine_individual_feature_preds.py %s %s\npython combine_feature_predicts.py %s %s\n' % (
        data_path, args.rank, data_path, args.rank))
        fn.close()
        system('bsub < %s' % lsf_fn)
        system('rm %s' % lsf_fn)
        system('rm %s' % jobs_fn)

    ### use GNU parallel if args.hpc == 'parallel'
    if args.hpc == 'parallel':
        sh_fn = 'run_%s_%s.sh' % (data_source_dir, data_name)
        fn = open(sh_fn, 'w')
        fn.write('#!/bin/bash\n')
        fn.write('parallel < {}\n'.format(jobs_fn))
        fn.write('python combine_individual_feature_preds.py %s %s\npython combine_feature_predicts.py %s %s\n' % (
            data_path, args.rank, data_path, args.rank))
        fn.close()
        system('sh %s' % sh_fn)
        system('rm %s' % sh_fn)
        system('rm %s' % jobs_fn)

    ### run sequentially otherwise
    else:
        system('sh %s' % jobs_fn)
        #system('rm %s' % jobs_fn)
    end = time()
    if (not args.hpc == 'minerva') and (not args.hpc == 'parallel'):
        print('Elapsed time is: %s seconds' % (end - start))
