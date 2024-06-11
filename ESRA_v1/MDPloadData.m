function [A_star_universe,Svec2id,Sid2vec,A,S]= MDPloadData(fileName)
 
file_path = fullfile('MDP_database',fileName );
rec=load(file_path);

A_star_universe=rec.A_star_universe;
Svec2id=rec.Svec2id;

Sid2vec=rec.Sid2vec;
A=rec.A;
S=rec.S;
 
end