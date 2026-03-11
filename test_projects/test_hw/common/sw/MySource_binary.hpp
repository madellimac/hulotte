#ifndef MYSOURCE_BINARY_H
#define MYSOURCE_BINARY_H

#include "streampu.hpp"

namespace spu
{
namespace module
{

class MySource_binary  : public Stateful {

private:
    
    int frame_size;
    int data_width;

public:

MySource_binary(int frame_size, int data_width);
    virtual ~MySource_binary();

protected:

    virtual void generate(int *output, const int frame_id);

};
}
}

#endif // MYSOURCE_BINARY_H